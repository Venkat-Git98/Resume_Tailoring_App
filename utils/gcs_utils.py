import os
import logging
import json # Make sure json is imported
from google.cloud import storage
from google.oauth2 import service_account # For explicit credential loading if needed
from typing import Optional # Import Optional if you use it for type hinting

# Your project's config
# python_file.py
import os
import json
try:
    import config as app_config
except ImportError:
    # ... fallback ...
    class FallbackConfig:
        SERVICE_ACCOUNT_JSON_CONTENT = "GOOGLE_CREDENTIALS_JSON_CONTENT"
    app_config = FallbackConfig()

env_var_name_to_look_for = app_config.SERVICE_ACCOUNT_JSON_CONTENT
actual_json_string_content = os.environ.get(env_var_name_to_look_for)

if actual_json_string_content:
    credentials_info = json.loads(actual_json_string_content)
    # ... etc.
else:
    logging.error(f"Environment variable '{env_var_name_to_look_for}' not set or empty.")

_gcs_client = None

def get_gcs_client(force_refresh=False):
    global _gcs_client
    if _gcs_client and not force_refresh:
        # logging.info("GCS_UTILS: Returning cached GCS client.") # Less verbose for frequent calls
        return _gcs_client

    logging.info("GCS_UTILS: Initializing Google Cloud Storage client...")
    
    env_var_name_for_json_content = getattr(app_config, 'GOOGLE_CREDENTIALS_ENV_VAR_NAME', 'GOOGLE_CREDENTIALS_JSON_CONTENT')
    creds_json_string = os.environ.get(env_var_name_for_json_content)
    
    try:
        if creds_json_string:
            credentials_info = json.loads(creds_json_string) 
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            project_id_from_creds = credentials_info.get("project_id")
            if not project_id_from_creds:
                logging.warning(f"GCS_UTILS: 'project_id' not found in service account JSON. GCS client will attempt to infer project.")

            _gcs_client = storage.Client(credentials=credentials, project=project_id_from_creds)
            logging.info(f"GCS_UTILS: Client created using credentials from env var '{env_var_name_for_json_content}'. Project: {project_id_from_creds or 'inferred'}")
        else:
            logging.error(f"GCS_UTILS: Env var '{env_var_name_for_json_content}' for GCS credentials not set. GCS client cannot be initialized with specific SA.")
            return None 
        
        return _gcs_client
    except json.JSONDecodeError:
        logging.error(f"GCS_UTILS: Failed to parse JSON content from env var '{env_var_name_for_json_content}'. Ensure it's valid JSON.", exc_info=True)
        _gcs_client = None
        return None
    except Exception as e:
        logging.error(f"GCS_UTILS: Error creating Storage client: {e}", exc_info=True)
        _gcs_client = None
        return None

def upload_file_to_gcs(gcs_client: storage.Client, local_file_path: str, gcs_file_path: str, bucket_name: Optional[str] = None) -> bool:
    """
    Uploads a local file to Google Cloud Storage.
    Args:
        gcs_client: The initialized GCS client.
        local_file_path: Path to the local file to upload.
        gcs_file_path: The desired "path"/name for the file within the GCS bucket.
        bucket_name: Optional. The name of the GCS bucket. If None, uses app_config.GCS_BUCKET_NAME.
    Returns:
        True if upload was successful, False otherwise.
    """
    if not gcs_client:
        logging.error(f"GCS_UTILS: GCS client not available (was None when passed). Cannot upload '{local_file_path}'.")
        return False

    if not os.path.exists(local_file_path):
        logging.error(f"GCS_UTILS: Local file not found for upload: {local_file_path}")
        return False

    actual_bucket_name = bucket_name if bucket_name else getattr(app_config, 'GCS_BUCKET_NAME', None)
    if not actual_bucket_name:
        logging.error("GCS_UTILS: Bucket name not provided and not found in app_config.")
        return False

    try:
        bucket = gcs_client.bucket(actual_bucket_name)
        blob = bucket.blob(gcs_file_path) # gcs_file_path is the "object name"

        logging.info(f"GCS_UTILS: Uploading '{local_file_path}' to bucket '{actual_bucket_name}' as '{gcs_file_path}'...")
        blob.upload_from_filename(local_file_path)
        logging.info(f"GCS_UTILS: File '{gcs_file_path}' uploaded successfully to bucket '{actual_bucket_name}'.")
        return True
    except Exception as e:
        logging.error(f"GCS_UTILS: Error uploading file '{local_file_path}' to '{gcs_file_path}' in bucket '{actual_bucket_name}': {e}", exc_info=True)
        return False