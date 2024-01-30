import boto3
import os

stsClient = boto3.client('sts')

metadataTable = os.getenv('METADATATABLE')
identityStore = os.getenv('IDENTITYSTOREID')
crossAccRole = os.getenv('CROSSACCROLE')

crossAcc = stsClient.assume_role(
    RoleArn = crossAccRole,
    RoleSessionName = "CKAMRevokePermission"
)
ACCESSKEY = crossAcc['Credentials']['AccessKeyId']
SECRETKEY = crossAcc['Credentials']['SecretAccessKey']
SESSIONTOKEN = crossAcc['Credentials']['SessionToken']

identityClient = boto3.client('identitystore', aws_access_key_id=ACCESSKEY, aws_secret_access_key=SECRETKEY, aws_session_token=SESSIONTOKEN)



def removeFromGroup(membershipId):
    try:
        response = identityClient.delete_group_membership(
            IdentityStoreId = identityStore,
            MembershipId = membershipId
        )
    except Exception as e:
        print('Not able to remove permission' + str(e))

def lambda_handler(event, context):
    membershipId = event['grantoutput']['Payload']['MembershipId']
    removeFromGroup(membershipId)
