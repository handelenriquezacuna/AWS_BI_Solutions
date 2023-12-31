import sys
import boto3
from botocore.client import Config
import pandas as pd
from io import BytesIO
import requests
import json
from collections import defaultdict
import re
import pandas

config = Config(retries = dict(max_attempts = 99))

# Initialize Boto3 clients for WorkDocs and Textract
workdocs = boto3.client('workdocs')
textract = boto3.client('textract',config=config)
s3_client = boto3.client('s3')

"""
Support functions
"""

def textract_waiter(job_id_forms):
  #This function is wait helper for the status processing    
    while True:
        forms_text_detection = textract.get_document_analysis(JobId=job_id_forms)
        try:
            status_forms = forms_text_detection['JobStatus']
        except:
            status_forms = 'No_Status'
            pass
        if status_forms == 'SUCCEEDED':
            break
        
    blocks_forms = forms_text_detection['Blocks']
    # print(blocks_forms)
    return blocks_forms

def text_value_extraction(blocks_forms):
#Full text value extraction 
    paragraphs = []
    current_paragraph = ""
    
    for block in blocks_forms:
        if block['BlockType'] == 'LINE':
            # Append text to the current paragraph
            current_paragraph += block['Text'] + ' '
        elif block['BlockType'] == 'WORD':
            # Add a space between words in the same line
            current_paragraph += block['Text'] + ' '
        elif block['BlockType'] == 'PARAGRAPH':
            # When a new paragraph block is encountered, add the current paragraph to the list
            paragraphs.append(current_paragraph.strip())
            current_paragraph = ""
    
    # Add the last paragraph (if any)
    if current_paragraph:
        paragraphs.append(current_paragraph.strip())
    
    # Now, 'paragraphs' contains a list of paragraphs extracted from the document
    # Display paragraphs
    for i, paragraph in enumerate(paragraphs, start=1):
        print(f"Paragraph {i}: {paragraph}")
    
    identifier = paragraph[-9:]
    identifier = re.findall(r'\d+', identifier)
    identifier_key = 'identifier'
    
    return identifier, identifier_key

def get_text(result, blocks_map):
    #Extracting Relationships between blocks
    text = ''
    if 'Relationships' in result:
        for relationship in result['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    if word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X'
    return text

def forms_extraction(blocks_forms):    
    # get key and value maps
    # kvs = key value stream
    try:
        key_map = {}
        value_map = {}
        block_map = {}
        for block in blocks_forms:
            block_id = block['Id']
            block_map[block_id] = block
            if block['BlockType'] == "KEY_VALUE_SET":
                if 'KEY' in block['EntityTypes']:
                    key_map[block_id] = block
                else:
                    value_map[block_id] = block
        
        kvs = defaultdict(list)
        for block_id, key_block in key_map.items():
            for relationship in key_block['Relationships']:
                if relationship['Type'] == 'VALUE':
                    for value_id in relationship['Ids']:
                        value_block = value_map[value_id]
                        # print(value_block)
                        key = get_text(key_block, block_map)
                        # print(key)
                        val = get_text(value_block, block_map)
                        # print(val)
                        kvs[key].append(val)
                        # print(kvs)
    except:
        kvs = ''
        pass
    return kvs

# S3 bucket name
s3_bucket_name = '{S3BUCKET}'
s3_resource = boto3.resource("s3")
s3_bucket = s3_resource.Bucket(s3_bucket_name)
files = s3_bucket.objects.all()
x = 1
final_df = pd.DataFrame()
for file in files:
    print(x)
    x = x + 1
    document_key = file.key
    """
    Reading all pdfs from S3 with textract
    """
    forms_textract_response = textract.start_document_analysis(DocumentLocation={'S3Object': {'Bucket': s3_bucket_name, 'Name': document_key}}, FeatureTypes=['FORMS'])
    job_id_forms = forms_textract_response['JobId']
    # print(job_id_forms)
    blocks_forms = textract_waiter(job_id_forms)
    identifier, identifier_key = text_value_extraction(blocks_forms)
    kvs = forms_extraction(blocks_forms)
    # Report Construction
    # print(identifier)
    for key, value in kvs.items():
        print(key, ":", value)
      
job.commit()
