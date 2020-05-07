import os
import boto3
import requests

from aws_lambda_powertools.logging import Logger, logger_inject_lambda_context
logger = Logger()

client = boto3.client('s3')

@logger.inject_lambda_context
def handler(event, context):
    """
    Args:
        url: Url of file to download
        chunk_size_in_MB: Size of chunks to download in (minimum 5MB, or completion will fail)
    return:
        location: Location of uploaded file
    """

    url = event.get('url', "https://upload.wikimedia.org/wikipedia/commons/f/ff/Pizigani_1367_Chart_10MB.jpg")
    chunk_size_in_MB = event.get('chunk_size', 5)
    key = url.split('/')[-1]
    bucket = os.environ['BUCKET_NAME']
    logger.info({"url": url, "chunk_size": chunk_size_in_MB, "bucket":bucket})
    location = main(
        url=url,
        chunk_size_in_MB=chunk_size_in_MB,
        key=key,
        bucket=bucket,
    )

    return location


def main(url, chunk_size_in_MB, key, bucket):
    """
    Downloads the file at the url provided in chunks, and uploads to <key> in <bucket>
    """

    upload_id = create_multipart_upload(bucket, key)
    parts = download_and_upload(url, upload_id, key, bucket, chunk_size_in_MB)
    location = complete_multipart_upload(key, bucket, upload_id, parts)

    return location

def create_multipart_upload(bucket, key):
    # Create Multipart upload
    response = client.create_multipart_upload(
        Bucket=bucket,
        Key=key,
        ServerSideEncryption='aws:kms',
    )
    upload_id = response['UploadId']
    logger.info({"message": "Multipart upload created", "upload_id": upload_id})
    return upload_id

def download_and_upload(url, upload_id, key, bucket, chunk_size_in_MB):
    parts = []

    # stream
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        logger.info({"headers": r.headers})

        # download & upload chunks
        for part_number, chunk in enumerate(r.iter_content(chunk_size=chunk_size_in_MB * 1024 * 1024)):
            response = client.upload_part(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number + 1,
                Body=chunk,
            )
            logger.debug({"UploadID": upload_id, "part_number": part_number + 1, "status": "uploaded"})
            parts.append({
                "ETag": response['ETag'],
                "PartNumber": part_number + 1,
            })
    logger.debug(parts)
    return parts

def complete_multipart_upload(key, bucket, upload_id, parts):
    # complete multipart upload
    print(f"Completed uploaded, closing multipart")
    response = client.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )

    location = response['Location']
    eTag = response['ETag']
    
    logger.debug(response)
    logger.info({"location": location, "eTag": eTag})

    return location
