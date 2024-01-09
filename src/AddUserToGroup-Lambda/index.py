import boto3
import os

identityClient = boto3.client('identitystore')
groupTable = os.getenv('GROUPTABLE')
identityStore = os.getenv('IDENTITYSTOREID')
dynamoClient = boto3.client('dynamodb')

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
            IdentityStoreId = 'd-90679c6abe',
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

    

def lambda_handler(event, context):
    requesterEmail = event['userEmail']
    permission = event['permissionType']

    groupId = getGroupId(permission)
    requesterId = getUserId(requesterEmail)
    assignPermission(requesterId, permission, groupId)


