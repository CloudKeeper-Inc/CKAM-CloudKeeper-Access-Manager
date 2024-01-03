import boto3
import os

approverTable = os.getenv('APPROVERTABLENAME')
requestTable = os.getenv('REQUESTTABLENAME')
sourceEmail = os.getenv('SESSOURCEEMAIL')
sourceArn = os.getenv('SESSOURCEARN')
dynamoClient = boto3.client('dynamodb')
dynamo = boto3.resource('dynamodb')
ses = boto3.client('ses')

def send_ses(toAddresses, subject, messageHtml):

    try:
        response = ses.send_email(
            Source = sourceEmail,
            SourceArn = sourceArn,
            Destination = {
                'ToAddresses': toAddresses
            },
            Message = {
                "Subject": {
                    "Data": subject, 
                    "Charset": "UTF-8"
                },
                "Body": {
                    "Html": {
                        "Data": messageHtml,
                        "Charset": "UTF-8"
                    }
                }
            }
        )
    except Exception as e:
        print('Error Sending Mail:' + str(e))



def lambda_handler(event, context):
    requestId = event['requestId']
    
    response = dynamoClient.get_item(
        TableName = requestTable,
        Key = {
            'requestId': {
                'N': requestId
            }
        }
    )
    
    requesterEmail = response['Item']['userEmail']['S']
    permission = response['Item']['permissionType']['S']
    duration = response['Item']['duration']['S']
    status = response['Item']['requestStatus']['S']

    table = dynamo.table(approverTable)
    response = table.scan()

    approvers = []
    for iter in response['Items']:
        approvers.append(iter['approverEmail'])

    match status.lower():
        case 'pending':
            toAddresses = approvers
            subject = f'CKAM - New Access Request for {permission}'
            messageHtml = f'<html><body><p><b>{requesterEmail}</b> requests access to AWS, please approve or reject this request.</p><p><b>Access:</b> {permission}<br /><b>Duration:</b> {duration}<br /></p></body></html>'
