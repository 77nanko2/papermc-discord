import os
from base64 import b64decode

import boto3
import requests
from botocore.exceptions import (BotoCoreError, ClientError,
                                 EndpointConnectionError, NoCredentialsError,
                                 ParamValidationError, PartialCredentialsError)


def lambda_handler(event: dict, context: object) -> str:
    """Lambda関数のエントリーポイント

    EC2インスタンスを起動し、起動状態を確認して
    DiscordにWebhookを送信します。

    Parameters
    ----------
    event : dict
        Lambda関数のイベントデータ
    context : object
        Lambdaランタイム情報を含むオブジェクト

    Returns
    -------
    str
        起動したEC2インスタンスのパブリックIPアドレス

    Raises
    ------
    ValueError
        環境変数が不足している場合
    BotoCoreError, ClientError
        AWS APIの操作に失敗した場合
    requests.RequestException
        Discord Webhookの送信に失敗した場合
    """

    try:
        # 環境変数の取得
        instance_id_encrypted = os.environ["INSTANCE_ID"]
        discord_webhook_url_encrypted = os.environ["DISCORD_WEBHOOK_URL"]
    except KeyError as e:
        raise ValueError(f"環境変数 {str(e)} が見つかりません") from e

    try:
        # KMSで暗号化されたEC2インスタンスIDの復号
        kms_client = boto3.client("kms")
        instance_id = kms_client.decrypt(
            CiphertextBlob=b64decode(instance_id_encrypted),
            EncryptionContext={
                "LambdaFunctionName": os.environ["AWS_LAMBDA_FUNCTION_NAME"]
            })["Plaintext"].decode("utf-8")

        # KMSで暗号化されたDiscord Webhook URLの復号
        discord_webhook_url = kms_client.decrypt(
            CiphertextBlob=b64decode(discord_webhook_url_encrypted),
            EncryptionContext={
                "LambdaFunctionName": os.environ["AWS_LAMBDA_FUNCTION_NAME"]
            })["Plaintext"].decode("utf-8")
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"KMS復号エラー: {str(e)}") from e

    try:
        # EC2クライアントの作成とインスタンス起動
        ec2 = boto3.client("ec2")

        # インスタンスの状態確認
        instance = ec2.describe_instances(InstanceIds=[instance_id])
        state = instance["Reservations"][0]["Instances"][0]["State"]["Name"]
        if state == "running":
            public_ip = instance["Reservations"][0]["Instances"][0].get("PublicIpAddress")
            data = {
                "content": f"インスタンス【{instance_id}】は起動済みです\r{public_ip}",
                "flags": 4096
            }
            res = f"{state} {public_ip}"
        elif state == "stopped":
            data = {
                "content": f"インスタンス【{instance_id}】は停止しています",
                "flags": 4096
            }
            res = state
        else:
            data = {
                "content": f"インスタンス【{instance_id}】のステータスは{state}です",
                "flags": 4096
            }
            res = state

    except (BotoCoreError,
            ClientError,
            NoCredentialsError,
            PartialCredentialsError,
            ParamValidationError,
            EndpointConnectionError) as e:
        raise RuntimeError(f"EC2操作エラー: {str(e)}") from e

    try:
        # DiscordにWebhookを送信
        requests.post(discord_webhook_url, json=data)
    except requests.RequestException as e:
        raise RuntimeError(f"Discord Webhook送信エラー: {str(e)}") from e

    return res


if __name__ == "__main__":
    pass
