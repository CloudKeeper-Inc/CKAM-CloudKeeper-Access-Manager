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
ssoAdminClient = boto3.client('sso-admin', aws_access_key_id=ACCESSKEY, aws_secret_access_key=SECRETKEY, aws_session_token=SESSIONTOKEN)


def removeFromApplication(membershipId):
    try:
        response = ssoAdminClient.delete_application_assignment(
            ApplicationArn='string',
            PrincipalId='string',
            PrincipalType='USER'
        )
    except Exception as e:
        print('Not able to remove permission' + str(e))

def lambda_handler(event, context):
    print(event)
    # membershipId = event['grantoutput']['Payload']['MembershipId']
    # removeFromApplication(membershipId)
