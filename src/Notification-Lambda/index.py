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
        case 'approved':
            toAddresses = [requesterEmail]
            subject = f'CKAM - Access Request approved for {permission}'
            messageHtml = f'<html><body><p>Access Approved for {permission}</p><p>Login to SSO Portal to access the account</p></body></html>'
        case 'rejected':
            toAddresses = [requesterEmail]
            subject = f'CKAM - Access Request Rejected for {permission}'
            messageHtml = f'<html><body><p>Access Request <b>Rejected</b> for {permission}</p><p>Contact Administrators for more Information</body></html>'
        case 'granted':
            toAddresses = [requesterEmail]
            subject = f'CKAM - Access Granted for {permission}'
            messageHtml = f'<html><body><p>Access Granted for {permission}</p><p><b>Duration: {duration}</b></p></body></html>'
        case 'completed':
            toAddresses = [requesterEmail]
            subject = f'CKAM - Access Duration Complete for {permission}'
            messageHtml = f'<html><body><p>Access Duration for {permission} Completed </p></body></html>'
        case 'expired':
            toAddresses = [requesterEmail]
            subject = f'CKAM - Access Request Expired for {permission}'
            messageHtml = f'<html><body><p>Access Request Expired for {permission}</p></body></html>'
        case 'cancelled':
            toAddresses = approvers + requesterEmail
            subject = f'CKAM - Access Request Cancelled for {permission}'
            messageHtml = f'<html><body><p>Access Request Cancelled for {permission}</p></body></html>'
        case _:
            print(f"Request status unexpected, exiting: {status.lower()}")
            exit()


    send_ses(toAddresses, subject, messageHtml)
