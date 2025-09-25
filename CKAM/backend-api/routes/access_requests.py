from flask import Blueprint, request, jsonify, g, current_app # <--- 'g' is now imported
import uuid
from slack_notifier import post_slack_approval_request

access_requests_bp = Blueprint('access_requests', __name__)

@access_requests_bp.route('/request', methods=['POST'])
def create_access_request():
    try:
        data = request.get_json()
        required_fields = ['userEmail', 'userName', 'permissionType', 'accessType', 'reason']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        jit_time_hours = float(data.get('jitTimeHours', 0))
        if data['accessType'] == 'Just-in-time' and jit_time_hours <= 0:
            return jsonify({"error": "JIT time must be a positive number for Just-in-time access"}), 400

        request_id = str(uuid.uuid4())
        duration_seconds = int(jit_time_hours * 3600)
        
        # --- Use g.dynamo_client instead of current_app.dynamo_client ---
        g.dynamo_client.put_item(
            TableName=current_app.config['REQUEST_TABLE_NAME'],
            Item={
                'requestId': {'S': request_id},
                'duration': {'N': str(duration_seconds)},
                'userEmail': {'S': data['userEmail']},
                'userName': {'S': data['userName']},
                'permissionType': {'S': data['permissionType']},
                'reason': {'S': data['reason']},
                'requestStatus': {'S': 'Pending'},
                'approver': {'S': ''},
                'approveReqMap': {'L': []}
            }
        )
        print(f"Successfully saved request {request_id} to DynamoDB.")

        approvers_table_name = current_app.config['APPROVER_TABLE_NAME']
        try:
            # --- Use g.dynamo_client instead of current_app.dynamo_client ---
            response = g.dynamo_client.scan(
                TableName=approvers_table_name,
                ProjectionExpression='slackUserId'
            )
            approver_slack_ids = [item['slackUserId']['S'] for item in response.get('Items', [])]
            if not approver_slack_ids:
                print("WARNING: No approvers found. No one will be notified.")
                return jsonify({"message": "Access request submitted successfully", "requestId": request_id}), 201
            print(f"Found {len(approver_slack_ids)} approvers to notify.")
        except Exception as e:
            print(f"ERROR: Could not scan the approvers table. Error: {e}")
            return jsonify({"error": "Request submitted, but failed to notify approvers."}), 500

        for user_id in approver_slack_ids:
            post_slack_approval_request(
                request_id=request_id, user_name=data['userName'],
                permission=data['permissionType'], jit_time=jit_time_hours,
                reason=data['reason'], access_type=data['accessType'],
                target_conversation_id=user_id
            )
        return jsonify({"message": "Access request submitted successfully", "requestId": request_id}), 201
    except Exception as e:
        print(f"ERROR in create_access_request: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

@access_requests_bp.route('/permissions', methods=['GET'])
def get_available_permissions():
    try:
        # --- Use g.dynamo_client instead of current_app.dynamo_client ---
        response = g.dynamo_client.scan(
            TableName=current_app.config['ACCESS_MANAGER_METADATA_TABLE'],
            ProjectionExpression='DisplayName'
        )
        display_names = sorted([item['DisplayName']['S'] for item in response['Items']])
        return jsonify({"permissions": display_names}), 200
    except Exception as e:
        print(f"ERROR in get_available_permissions: {e}")
        return jsonify({"error": "Failed to retrieve permissions from AWS."}), 500
