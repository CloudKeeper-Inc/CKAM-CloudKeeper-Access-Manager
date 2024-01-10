import boto3
import os

requestTable = os.getenv('REQUESTTABLENAME')
dynamoClient = boto3.client('dynamodb')

def updateRequestStatus(requestId):
    response = dynamoClient.update_item(
        TableName = requestTable,
        
        ExpressionAttributeNames = {
            '#RS': 'requestStatus'
        },
        ExpressionAttributeValues = {
            ':u' : {
                'S': 'Expired'
            }
        },
        Key = {
            'requestId': {
                'N': requestId
            }
        },
        UpdateExpression='SET #RS = :u'
    )


def lambda_handler(event, context):
    requestId = event['requestId']

    updateRequestStatus(requestId)