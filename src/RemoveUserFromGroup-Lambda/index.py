import boto3
import os

stsClient = boto3.client('sts')

metadataTable = os.getenv('METADATATABLE')
identityStore = os.getenv('IDENTITYSTOREID')
crossAccRole = os.getenv('CROSSACCROLE')

dynamoClient = boto3.client('dynamodb')

crossAcc = stsClient.assume_role(
    RoleArn = crossAccRole,
    RoleSessionName = "CKAMRevokePermission"
)
ACCESSKEY = crossAcc['Credentials']['AccessKeyId']
SECRETKEY = crossAcc['Credentials']['SecretAccessKey']
SESSIONTOKEN = crossAcc['Credentials']['SessionToken']

identityClient = boto3.client('identitystore', aws_access_key_id=ACCESSKEY, aws_secret_access_key=SECRETKEY, aws_session_token=SESSIONTOKEN)
ssoAdminClient = boto3.client('sso-admin', aws_access_key_id=ACCESSKEY, aws_secret_access_key=SECRETKEY, aws_session_token=SESSIONTOKEN)

def getApplicationArn(permission):
    response = dynamoClient.get_item(
        TableName = metadataTable,
        Key = {
            'DisplayName': {
                'S': permission
            }
        }
    )

    applicationArn = response['Item']['ApplicationArn']['S']

    return applicationArn

def getUserId(requesterEmail):
    response = identityClient.list_users(
        IdentityStoreId = identityStore,
    )
    users = response['Users']

    while 'NextToken' in response:
        response = identityClient.list_users(
            IdentityStoreId = identityStore,
            NextToken = response['NextToken']
        )
        users.extend(response['Users'])

    userId = ''
    for user in users:
        for userEmail in user['Emails']:
            if userEmail['Value'] == requesterEmail:
                userId = user['UserId']

    return userId

def removeFromApplication(applicationArn, principalId):
    try:
        response = ssoAdminClient.delete_application_assignment(
            ApplicationArn=applicationArn,
            PrincipalId=principalId,
            PrincipalType='USER'
        )
    except Exception as e:
        print('Not able to remove permission' + str(e))

def lambda_handler(event, context):
    permission = event["data"]["Item"]["permissionType"]["S"]
    requesterEmail = event["data"]["Item"]["userEmail"]["S"]

    applicationArn = getApplicationArn(permission)
    userId = getUserId(requesterEmail)

    removeFromApplication(applicationArn, userId)
    print('User:' + requesterEmail + 'removed from application:' + permission)
