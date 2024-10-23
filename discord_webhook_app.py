import json
import os
from base64 import b64decode

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def lambda_handler(event: dict, context: dict) -> dict:
    """
    Discordインタラクションを処理するAWS Lambdaハンドラ関数

    Parameters
    ----------
    event : dict
        HTTPリクエストの詳細を含むAWS Lambdaのイベント
    context : dict
        Lambda関数が呼び出されるコンテキスト

    Returns
    -------
    dict
        適切なステータスコードと本文を含むHTTPレスポンス
    """

    public_key = decrypt_env_varibles()

    try:
        body = json.loads(event['body'])

        signature = event['headers']['x-signature-ed25519']
        timestamp = event['headers']['x-signature-timestamp']
        verify_key = VerifyKey(bytes.fromhex(public_key))
        message = timestamp + event['body']
        try:
            verify_key.verify(message.encode(), signature=bytes.fromhex(signature))
        except BadSignatureError:
            return {
                'statusCode': 401,
                'body': json.dumps('invalid request signature')
            }

        # PING
        # アプリにInteractions Endpoint URLを登録する際に、
        # PINGリクエストに対しPONG応答を返して認証を完了させる
        if body["type"] == 1:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'type': 1
                })
            }

        # APPLICATOIN_COMMAND
        # アプリケーションコマンドが送られてくるのでコマンド処理
        elif body["type"] == 2:
            return command_handler(body)

        # MESSAGE_COMPONENT, APPLICATION_COMMAND_AUTOCOMPLETE, MODAL_SUBMIT
        # 期待してないリクエストなのでBad Request(400)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps('unhandled request type')
            }

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise


def decrypt_env_varibles() -> str:
    try:
        # DISCORD_PUBLIC_KEYを復号
        kms_client = boto3.client("kms")
        public_key_encrypted = os.environ["DISCORD_PUBLIC_KEY"]
        public_key = kms_client.decrypt(
            CiphertextBlob=b64decode(public_key_encrypted),
            EncryptionContext={
                "LambdaFunctionName": os.environ["AWS_LAMBDA_FUNCTION_NAME"]
            })["Plaintext"].decode("utf-8")
        return public_key
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"KMS復号エラー: {str(e)}") from e


def command_handler(body: dict) -> dict:
    """
    Discordアプリケーションコマンドを処理します

    Parameters
    ----------
    body : dict
        コマンドの詳細を含むHTTPリクエストの本文

    Returns
    -------
    dict
        適切なステータスコードとコマンド実行結果を含むHTTPレスポンス
    """
    command = body['data']['name']
    action = body["data"]["options"][0]["value"]

    if command == "server":
        # インスタンス起動処理
        if action == "start":
            return invoke_lambda_function("discord-start-instance", "サーバーを起動しています・・・")
        # インスタンス停止処理
        elif action == "stop":
            return invoke_lambda_function("discord-stop-instance", "サーバーを停止しています・・・")
        # インスタンスステータス取得処理
        elif action == "status":
            return invoke_lambda_function("discord-check-instance", "サーバーステータスを取得しています・・・")

    # 想定されているコマンド以外はBad Request(400)
    return {
        'statusCode': 400,
        'body': json.dumps('Unhandled command')
    }


def invoke_lambda_function(function_name: str, success_message: str) -> dict:
    """
    指定されたLambda関数を非同期で呼び出します

    Parameters
    ----------
    function_name : str
        呼び出すLambda関数の名前
    success_message : str
        呼び出し成功時に返すメッセージ

    Returns
    -------
    dict
        コマンド実行結果を示すHTTPレスポンス
    """
    boto3.client("lambda").invoke(
        FunctionName=function_name,
        InvocationType="Event",
    )
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': 4,
            'data': {
                'content': success_message,
                'flags': 4096
            }
        })
    }
