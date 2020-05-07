# Downloading Large Files with Lambda

Lambda functions (regardless of size) have 512MB of disk space in the `/tmp` directory. Which means downloading and uploading files less than 512MB is a simple task.

But what if you need more? In this repo, we'll show you how to download a 1.3GB file into an S3 bucket using lambda.

# Setup

    $ cd terraform
    $ terraform apply --auto-approve
    $ cd ../serverless
    $ sls deploy

First we have to setup our s3 bucket and lambda function. For the bucket, we'll use Terraform. Terraform has a few advantages over Cloudformation here, namely:

* We can more easily setup advance settings like lifecycle policy and kms encryption
* We can set `force-destroy` on a bucket, to allow us easily cleanup afterwards
* I just prefer here...don't @ me :)

Once our bucket is created, we then deploy the lambda function. For this, we use Serverless Framework, which has advantages over Terraform namely:

* It's far more opionated, which means we have to tinker less
* It's more suited for Lambda than Terraform
* I just prefer it over Terraform for lambdas ... don't @ me :)

# What we installed

Now, once we setup everything -- we'll have:

* Randomly named bucket that begins with multipart-test, which has
    - KMS encryption turned on with the default aws/S3 CMK
    - A lifecycle policy, that expires all multi-part uploads that haven't completed after 1 day
    - Versioining turned on
* Two SSM parameters, holding the bucket name and bucket arn values
* A lambda function that can access the internet, and:
    - s3:PutObject on the bucket
    - multiple kms permissions for the default aws/s3 key

# How it works

As mentioned lambda only has 512MB of space on disk, so we have two options, download the file to memory (which can be expanded to 3008MB) or download the file incrementally in chunks.

We choose the chunk option, effectively downloading x MB at a time, and using s3 multipart upload to upload the files to in chunks to S3. We then complete the multi-part upload, and voila, our small lambda can downloads Gigabytes from the internet, and store it in S3.

The real magic comes from this bit of code, which uses the Python Requests library, to download the file from the internet in chunks, and for every chunks uploads it as a 'part' to S3. This way, the lambda only has to support the size of the part, and not the entire file.

```python
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
```

# KMS Encryption

It annoys me, that AWS typically run 'hello-world' examples on their blog, which unfortunately get copied lock-stock n' barrel into people's production environment.

KMS encryption for S3 is pretty straightforward, and should be the default setting for all your production buckets.

But KMS encryption with multi-part upload is a slightly different beast, as it requires additional permissions, as can be gleaned from the boto3 documentation:

    To perform a multipart upload with encryption using an AWS KMS CMK, the requester must have permission to the kms:Encrypt , kms:Decrypt , kms:ReEncrypt* , kms:GenerateDataKey* , and kms:DescribeKey actions on the key. These permissions are required because Amazon S3 must decrypt and read data from the encrypted file parts before it completes the multipart upload.

So in order to grant our Lambda the right permission, we provide the following:

```yaml
  iamRoleStatements:
  - Effect: Allow
    Action: s3:PutObject
    Resource: ${ssm:${self:custom.ssm_prefix}/${self:custom.bucket_logical_name}/arn}/*
  - Effect: Allow
    Action:
      - kms:Encrypt
      - kms:Decrypt
      - kms:ReEncrypt*
      - kms:GenerateDataKey*
      - kms:DescribeKey
    Resource:
      Fn::Join:
        - ":"
        - - arn:aws:kms
          - ${self:provider.region}  
          - Ref: AWS::AccountId
          - alias/aws/s3 #default aws/S3 key
```

In the above, we grant the lambda `s3:PutObject` for the bucket, but also access to the KMS encryption key. For this, we reference the key alias of the default S3 CMK (aws/s3), but you can swap that out for any alias or key you wish. We also use the `Ref: AWS::AccountId` to make our code more generic, but also allows me to now paste my account id on GitHub repos :)

# Getting the big file

By default, the lambda will try to download a ~10MB file from wikipedia, this is mostly for testing purposes. The file is downloaded in chunks of 5MB (the smallest chunk size possible), and multi-part uploaded to S3.

For a larger file, we can use the following command for serverless framework:

    $ sls invoke -f download_big_file -d '{"url":"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/index.json", "chunk_size": 256}'

This downloads a ~1.3GB file from aws in us-east-1 (hence why I default the region to us-east-1), totally in memory, via multi-part upload with parts of size 256. The operation typically takes 20-30 seconds to complete, and the final result is the 1.3GB file in your S3 bucket (with default KMS encryption turned on)

# Uninstall

To uninstall

    $ cd serverless
    $ serverless remove
    $ cd terraform
    $ terraform destroy

Nothing will be left in your account! :)