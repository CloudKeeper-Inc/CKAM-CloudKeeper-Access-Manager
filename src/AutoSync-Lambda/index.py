import boto3
import os

identityStore = os.getenv('IDENTITYSTOREID')
crossAccRole = os.getenv('CROSSACCROLE')
metdataTable = os.getenv('METADATATABLE')


dynamoClient = boto3.client('dynamodb')
stsClient = boto3.client('sts')
crossAcc = stsClient.assume_role(
    RoleArn = crossAccRole,
    RoleSessionName = 'CKAMAutoSyncLambda'
)
ACCESSKEY = crossAcc['Credentials']['AccessKeyId']
SECRETKEY = crossAcc['Credentials']['SecretAccessKey']
SESSIONTOKEN = crossAcc['Credentials']['SessionToken']

identityClient = boto3.client(
    'identitystore', 
    aws_access_key_id = ACCESSKEY, 
    aws_secret_access_key = SECRETKEY, 
    aws_session_token = SESSIONTOKEN
)

def updateDynamo(groups):
    for group in groups:
        dynamoClient.put_item(
            TableName = metdataTable,
            Item = {
                'GroupId': {
                    'S': group['GroupId']
                },
                'DisplayName': {
                    'S': group['DisplayName']
                },
                'IdentityStoreId': {
                    'S': group['IdentityStoreId']
                }
            }
        )


def getGroupDetails():
    response = identityClient.list_groups(
        IdentityStoreId = identityStore,
    )
    groups = response['Groups']

    while 'NextToken' in response:
        response = identityClient.list_groups(
            IdentityStoreId = identityStore,
            NextToken = response['NextToken']
        )
        groups.extend(response['Groups'])
        
    return groups

def lambda_handler(event, context):
    groups = getGroupDetails()
    updateDynamo(groups)