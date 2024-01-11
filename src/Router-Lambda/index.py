import boto3
import json
import os

grantStateMachine = os.getenv('GRANTSTATEMACHINEARN')
approvalStateMachine = os.getenv('APPROVALSTATEMACHINEARN')
rejectStateMachine = os.getenv('REJECTSTATEMACHINEARN')
revokeStateMachine = os.getenv('REVOKESTATEMACHINEARN')
requestTableName = os.getenv('REQUESTTABLENAME')
approverTableName = os.getenv('APPROVERTABLENAME')
fnNotificationsArn = os.getenv('NOTIFICATIONLAMBDA')
fnStatusArn = os.getenv('STATUSLAMBDA')

ckam_config = {
    "requests_table": requestTableName,
    "revoke_sm": revokeStateMachine,
    "grant_sm": grantStateMachine,
    "fn_teamnotifications_arn": fnNotificationsArn,
    "fn_teamstatus_arn": fnStatusArn
}

def pendingFlow(requestId):
    sfnClient = boto3.client('stepfunctions')
    ckam_config["requestId"] = requestId

    try:
        response = sfnClient.start_execution(
            stateMachineArn = approvalStateMachine,
            input = json.dumps(ckam_config)
        )
    except Exception as e:
        print("Error:" + str(e))


def approvedFlow():
    sfnClient = boto3.client('stepfunctions')

    try:
        response = sfnClient.start_execution(
            stateMachineArn = grantStateMachine,
            input = "{}"
        )
    except Exception as e:
        print("Error:" + str(e))

def rejectedFlow(requestId, requestStatus):
    sfnClient = boto3.client('stepfunctions')
    ckam_config["status"] = requestStatus
    ckam_config["requestId"] = requestId

    try:
        response = sfnClient.start_execution(
            stateMachineArn = rejectStateMachine,
            input = json.dumps(ckam_config)
        )
    except Exception as e:
        print("Error:" + str(e))

def extractEvents(event):
    event = event["Records"][0]["dynamodb"]["NewImage"]
    ssnDuration = event["duration"]['S']
    usrEmail = event["userEmail"]['S']
    permission = event["permissionType"]['S']
    usrName = event["name"]['S']
    requestStatus = event["requestStatus"]['S']
    requestId = event["requestId"]['N']
    
    if requestStatus.lower() == "pending":
        print('[INFO] Pending Flow Invoked')
        pendingFlow(requestId)
    elif requestStatus.lower() == "approved":
        print('[INFO] Approved Flow Invoked')
        approvedFlow()
    elif requestStatus.lower() in ["rejected", "cancelled"]:
        print('[INFO] Rejection/Cancellation Flow Invoked')
        rejectedFlow(requestId, requestStatus)
    else:
        pass
    
def lambda_handler(event, context):
    extractEvents(event)