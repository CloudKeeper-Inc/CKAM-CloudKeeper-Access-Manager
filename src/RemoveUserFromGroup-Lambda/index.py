import boto3
import os

identityClient = boto3.client('identitystore')
groupTable = os.getenv('GROUPTABLE')
identityStore = os.getenv('IDENTITYSTOREID')

def removeFromGroup(membershipId):
    try:
        response = identityClient.delete_group_membership(
            IdentityStoreId = identityStore,
            MembershipId = membershipId
        )
    except Exception as e:
        print('Not able to remove permission' + str(e))

def lambda_handler(event, context):
    membershipId = event['MembershipId']
    removeFromGroup(membershipId)
