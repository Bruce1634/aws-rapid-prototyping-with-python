from typing import Any, Dict, Tuple

import boto3
from botocore.exceptions import ClientError

import json
import uuid


dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url='http://localhost:8000',  # TODO: Refer env var or something instead
    # endpoint_url='http://dynamodb:8000',  # TODO: Refer env var or something instead
)
table = dynamodb.Table('testUserTable')  # TODO: Refer env var or something instead

EventType = Dict[str, Any]
ContextType = Dict[str, Any]
ResponseType = Dict[str, object]


class UserHandler:
    @classmethod
    def dispatch(cls, event: EventType) -> ResponseType:
        try:
            status_code, body = getattr(cls, event['httpMethod'].lower())(event)
        except AttributeError:
            status_code, body = 405, {'message': 'METHOD NOT ALLOWED'}

        return {'statusCode': status_code, 'body': json.dumps(body)}

    @classmethod
    def get(cls, event: EventType) -> Tuple[int, Dict[str, str]]:
        user_id = event['pathParameters']['user_id']

        try:
            response = table.get_item(Key={'user_id': user_id})
        except ClientError:
            raise  # TODO: Implement appropriate error handling

        if 'Item' not in response:
            return 404, {'message': 'No such user found'}

        return 200, response['Item']

    @classmethod
    def put(cls, event: EventType) -> Tuple[int, Dict[str, str]]:
        parameters = json.loads(event['body'])
        item = {'user_id': uuid.uuid4().hex, 'name': parameters['name']}

        try:
            table.put_item(Item=item)
        except ClientError:
            raise  # TODO: Implement appropriate error handling

        return 201, item

    @classmethod
    def delete(cls, event: EventType) -> Tuple[int, Dict[str, str]]:
        user_id = event['pathParameters']['user_id']

        try:
            table.delete_item(Key={'user_id': user_id})
        except ClientError:
            raise  # TODO: Implement appropriate error handling

        return 204, {}

    @classmethod
    def patch(cls, event: EventType) -> Tuple[int, Dict[str, str]]:
        user_id = event['pathParameters']['user_id']
        parameters = json.loads(event['body'])

        try:
            response = table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET #nm = :newname',
                ExpressionAttributeNames={'#nm': 'name'},
                ExpressionAttributeValues={':newname': parameters['name'], ':user_id': user_id},
                ConditionExpression='user_id = :user_id',
                ReturnValues='UPDATED_NEW',
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return 404, {'message': 'No such user found'}
            raise

        return 200, {'user_id': user_id, 'name': response['Attributes']['name']}


PATHS = {
    '/user': UserHandler,
    '/user/{user_id}': UserHandler,
}


def dispatch_request(event: EventType, context: ContextType) -> ResponseType:
    request_path = event['requestContext']['path']
    if request_path not in PATHS:
        return {'statusCode': 404, 'body': json.dumps({'message': 'NOT FOUND'})}

    return PATHS[request_path].dispatch(event)
