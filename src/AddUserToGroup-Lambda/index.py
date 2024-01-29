import boto3
import os

groupTable = os.getenv('GROUPTABLE')
identityStore = os.getenv('IDENTITYSTOREID')
crossAccRole = os.getenv('CROSSACCROLE')

dynamoClient = boto3.client('dynamodb')
stsClient = boto3.client('sts')

crossAcc = stsClient.assume_role(
    RoleArn = crossAccRole,
    RoleSessionName = "CKAMGrantPermission"
)
ACCESSKEY = crossAcc['Credentials']['AccessKeyId']
SECRETKEY = crossAcc['Credentials']['SecretAccessKey']
SESSIONTOKEN = crossAcc['Credentials']['SessionToken']

identityClient = boto3.client('identitystore', aws_access_key_id=ACCESSKEY, aws_secret_access_key=SECRETKEY, aws_session_token=SESSIONTOKEN)

def getGroupId(permission):
    response = dynamoClient.get_item(
        TableName = groupTable,
        Key = {
            'accountName': {
                'S': permission
            }
        }
    )

    groupId = response['Item']['groupId']['S']

    return groupId

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

def assignPermission(requesterId, permission, groupId):
    try:
        response = identityClient.create_group_membership(
            IdentityStoreId = identityStore,
            GroupId = groupId,
            MemberId = {
                'UserId': requesterId
            }
        )
    except Exception as e:
        print(f"Can't assign user to {permission}" + str(e))

    return response

    

def lambda_handler(event, context):
    requesterEmail = event['userEmail']
    permission = event['permissionType']

    groupId = getGroupId(permission)
    requesterId = getUserId(requesterEmail)
    response = assignPermission(requesterId, permission, groupId)

    return response


