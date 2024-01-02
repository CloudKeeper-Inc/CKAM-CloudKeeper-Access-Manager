import boto3
import json
import os

grantStateMachine = os.getenv('GRANTSTATEMACHINEARN')
approvalStateMachine = os.getenv('APPROVALSTATEMACHINEARN')
rejectStateMachine = os.getenv('REJECTSTATEMACHINEARN')
revokeStateMachine = os.getenv('REVOKESTATEMACHINE')
requestTableName = os.getenv('REQUESTTABLENAME')
fnNotificationsArn = os.getenv('NOTIFICATIONLAMBDA')

team_config = {
    "requests_table": requestTableName,
    "revoke_sm": revokeStateMachine,
    "grant_sm": grantStateMachine,
    "fn_teamnotifications_arn": fnNotificationsArn,
}

def pendingFlow():
    sfnClient = boto3.client('stepfunctions')

    try:
        response = sfnClient.start_exectution(
            stateMachineArn = approvalStateMachine,
            input = "{}"
        )
    except Exception as e:
        print("Error:" + e)


def approvedFlow():
    sfnClient = boto3.client('stepfunctions')

    try:
        response = sfnClient.start_exectution(
            stateMachineArn = grantStateMachine,
            input = "{}"
        )
    except Exception as e:
        print("Error:" + e)

def rejectedFlow():
    sfnClient = boto3.client('stepfunctions')

    try:
        response = sfnClient.start_exectution(
            stateMachineArn = rejectStateMachine,
            input = "{}"
        )
    except Exception as e:
        print("Error:" + e)

def extractEvents(event):
    event = event["Records"][0]["dynamodb"]["NewImage"]
    ssnDuration = event["duration"]
    usrEmail = event["userEmail"]
    permission = event["permissionType"]
    usrName = event["name"]
    requestStatus = event["requestStatus"]
    
    if requestStatus.lower() == "pending":
        pendingFlow()
    elif requestStatus.lower() == "approved":
        approvedFlow()
    elif requestStatus.lower() == "rejected":
        rejectedFlow()
    else:
        rejectedFlow()
    
def lambda_handler(event, context):
    extractEvents(event)