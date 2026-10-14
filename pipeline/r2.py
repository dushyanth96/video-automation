"""R2 upload helper. Uses boto3 if installed, else curl-style S3 REST note.
Usage: python -m pipeline.r2 upload output/dialogue_reel.mp4 renders/2026-10-14.mp4 [--public]
"""
import argparse, os, sys
try:
    from pipeline.env import load_project_env; load_project_env()
except Exception:
    pass

def cfg():
    return {
        "account": os.getenv("R2_ACCOUNT_ID", ""),
        "key": os.getenv("R2_ACCESS_KEY_ID", ""),
        "secret": os.getenv("R2_SECRET_ACCESS_KEY", ""),
        "bucket": os.getenv("R2_BUCKET", "videos-automation"),
        "endpoint": os.getenv("R2_ENDPOINT", ""),
        "public": os.getenv("R2_PUBLIC_URL", "").rstrip("/"),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["upload"])
    ap.add_argument("local")
    ap.add_argument("remote")
    args = ap.parse_args()
    c = cfg()
    if not (c["account"] and c["key"] and c["secret"]):
        sys.exit("R2 keys missing. Fill .env (see README section 2).")
    endpoint = c["endpoint"] or f"https://{c['account']}.r2.cloudflarestorage.com"
    try:
        import boto3
        s3 = boto3.client("s3", endpoint_url=endpoint,
                          aws_access_key_id=c["key"], aws_secret_access_key=c["secret"])
        s3.upload_file(args.local, c["bucket"], args.remote,
                       ExtraArgs={"ContentType": "video/mp4"})
        url = f"{c['public']}/{args.remote}" if c["public"] else f"r2://{c['bucket']}/{args.remote}"
        print(url)  # workflows capture this as preview URL
    except ImportError:
        sys.exit("pip install boto3  (uv pip install boto3) then retry.")

if __name__ == "__main__":
    main()
