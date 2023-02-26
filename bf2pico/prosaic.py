"""
    I provide the prosaic functions for bf2pico.
"""


import json
import logging
import smtplib


from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


import boto3


from botocore.exceptions import ClientError


from bf2pico import (
    BUCKET,
    CACHE,
    LOG,
    MAIL_SERVER,
    PERSISTENT_CACHE_TIME,
)


logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)


S3 = boto3.client('s3')
SSM = boto3.client('ssm')


def delete_parameter(name: str) -> None:
    """ I de;ete a parameter from parameter store

    Args:
        name (str): parameter name
    """
    response = SSM.delete_parameter(Name=name)
    LOG.debug(json.dumps(response, default=str))
    for param in list(CACHE):
        if param.startswith('parameters-'):
            LOG.debug('Clearing Parameter')
            CACHE.pop(param)


def put_parameter(name: str, value: str) -> None:
    """ I add parameters to parameter store

    Args:
        name (str): parameter name
        value (str): parameter value
    """
    response = SSM.put_parameter(
        Name=name,
        Description=f'for {name}',
        Value=value,
        Type='SecureString',
        Overwrite=True,
        Tier='Standard',
        DataType='text'
    )
    LOG.debug(json.dumps(response, default=str))
    for param in list(CACHE):
        if param.startswith('parameters-'):
            LOG.debug('Clearing Parameter %s', param)
            CACHE.pop(param)


def get_parameters(path: str) -> dict:
    """ I return the parameters for a path

    Returns:
        dict: parameter store values
            {
                parameter name: parameter value
            }
    """
    if CACHE.get(f'parameters-{path}', None):
        return json.loads(CACHE.get(f'parameters-{path}'))
    result = {}
    response = SSM.get_parameters_by_path(
        Path=path,
        Recursive=True,
        WithDecryption=True
    )
    for param in response['Parameters']:
        result[param['Name'].split('/')[-1]] = param['Value']
    if response.get('NextToken',  None):
        response = SSM.get_parameters_by_path(
            Path=path,
            Recursive=True,
            WithDecryption=True,
            NextToken=response['NextToken']
        )
        for param in response['Parameters']:
            result[param['Name'].split('/')[-1]] = param['Value']
    CACHE.set(
        f'parameters-{path}',
        json.dumps(result),
        expire=PERSISTENT_CACHE_TIME
    )
    return result


def s3_getobjects(path: str) -> list:
    """ I return the objects in a path

    Args:
        path (str): The path to list

    Returns:
        list: list of objects in a bucket path
    """
    result = []
    LOG.debug('Looking for object in s3://%s/%s', BUCKET, path)
    response = S3.list_objects_v2(
        Bucket=BUCKET,
        Prefix=path,
        FetchOwner=False,
    )
    for record in response.get('Contents', []):
        result.append(record['Key'])
    while response.get('NextContinuationToken', None):
        response = S3.list_objects_v2(
            Bucket=BUCKET,
            NextContinuationToken=response['NextContinuationToken']
        )
        for record in response.get('Contents', []):
            result.append(record['Key'])
    return result


def s3_put(data, key) -> None:
    """
        I write to the bucket the job data.

        Args:
            data: the contexts to write in the object.
            key: the object key to write.
    """
    cache_key = f's3-{key}'
    cache_value = CACHE.get(cache_key, '')
    if cache_value and  cache_value == data:
        LOG.debug('skipping s3 as the value is the same')
    else:
        LOG.info('uploading s3://%s/%s', BUCKET, key)
        result = S3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=data,
            ACL='bucket-owner-full-control'
        )
        CACHE.set(cache_key, data, expire=PERSISTENT_CACHE_TIME)
        LOG.debug(json.dumps(result, default=str))


def s3_get(key: str, default=None) -> str:
    """
        I return the contexts of a s3 object.

        Args:
            key (str): the key to for the object to fetch
            default (type): What to use as the default if key doesn't exist.

        Returns:
            the contexts of the object
    """
    LOG.debug('fetching s3://%s/%s', BUCKET, key)
    if f's3-{key}' in CACHE:
        return CACHE.get(f's3-{key}')
    try:
        obj = S3.get_object(Bucket=BUCKET, Key=key)
        result = obj['Body'].read().decode('utf8')
        CACHE.set(f's3-{key}', result, expire=PERSISTENT_CACHE_TIME)
        return result
    except ClientError as err_msg:
        if err_msg.response['Error']['Code'] == 'NoSuchKey':
            return default
        raise


def email(
        mail_to: str,
        mail_from: str,
        mail_subject: str='Pico Brew',
        mail_body: str='',
        image_file: str=''
    ) -> None:
    """_summary_

    Args:
        mail_to (str): The mail receiver
        mail_from (str): The mail sender
        mail_subject (str): The subject of the mail
        mail_body (str, optional): The text mail body
        image_file (str, optional): The local file to send. Defaults to ''
    """

    msg = MIMEMultipart()
    msg['From'] = mail_from
    msg['To'] = mail_to
    msg['Subject'] = mail_subject
    msg.preamble = mail_subject

    if image_file:
        with open(image_file, 'rb') as image_handler:
            img = MIMEImage(image_handler.read())
        msg.attach(img)

    if mail_body:
        part1 = MIMEText(mail_body, 'plain')
        msg.attach(part1)

    with smtplib.SMTP(MAIL_SERVER) as mail_handler:
        mail_handler.sendmail(mail_to, mail_from, msg.as_string())
