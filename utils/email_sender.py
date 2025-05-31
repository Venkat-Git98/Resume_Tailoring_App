# Resume_Tailoring/utils/email_sender.py
import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate
from typing import Optional, List

# Attempt to import config from the project root
config = None # Initialize
try:
    import config
    logging.info("email_sender: Successfully imported app_config.")
except ImportError as e:
    logging.warning(f"email_sender: Could not import app_config via absolute import: {e}. Email sender might not have correct default settings.")
    # config remains None

logger = logging.getLogger(__name__)

def send_job_application_email(
    subject: str,
    body: str,
    recipient_email: str,
    # Parameters for overriding settings from config.py
    displayed_from_email_override: Optional[str] = None,
    smtp_login_override: Optional[str] = None,
    smtp_key_override: Optional[str] = None, # Allows direct key override
    attachments: Optional[List[str]] = None,
    smtp_server_override: Optional[str] = None,
    smtp_port_override: Optional[int] = None
) -> bool:
    """
    Sends an email with optional attachments using Brevo SMTP settings,
    primarily sourced from config.py.
    """
    if not attachments:
        attachments = []

    # --- Get Brevo SMTP Configuration from config.py or use overrides ---
    cfg_smtp_server = getattr(config, "BREVO_SMTP_SERVER", "smtp-relay.brevo.com")
    cfg_smtp_port = getattr(config, "BREVO_SMTP_PORT", 587)
    cfg_smtp_login = getattr(config, "BREVO_SMTP_LOGIN", "8dcd12002@smtp-brevo.com") # Default from your info
    cfg_sender_display_email = getattr(config, "BREVO_SENDER_DISPLAY_EMAIL", "default_sender@example.com") # Ensure a fallback

    # Determine SMTP Key: Prioritize override, then env var, then config fallback
    cfg_smtp_key_env_var_name = getattr(config, "BREVO_SMTP_KEY_ENV_VAR_NAME", "BREVO_SMTP_KEY")
    cfg_smtp_key_fallback = getattr(config, "BREVO_SMTP_KEY_FALLBACK_FOR_TESTING", None)
    
    final_smtp_key = smtp_key_override or os.getenv(cfg_smtp_key_env_var_name) or cfg_smtp_key_fallback

    # Determine final values to use
    final_smtp_server = smtp_server_override or cfg_smtp_server
    final_smtp_port = smtp_port_override or cfg_smtp_port
    final_smtp_login = smtp_login_override or cfg_smtp_login
    final_displayed_from_email = displayed_from_email_override or cfg_sender_display_email
    
    if not final_smtp_login: 
        logger.error("Brevo SMTP login (username) is not configured in config.py or via override.")
        return False
    if not final_displayed_from_email:
        logger.error("Displayed 'From' email address is not configured in config.py or via override.")
        return False
    if not final_smtp_key: 
        logger.error(
            "CRITICAL: Brevo SMTP key (Password) could not be resolved from override, "
            f"environment variable ('{cfg_smtp_key_env_var_name}'), or config.py fallback."
        )
        return False
    if not recipient_email:
        logger.error("Recipient email not provided.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = final_displayed_from_email 
        msg['To'] = recipient_email
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', _charset='utf-8'))

        for file_path in attachments:
            if not os.path.exists(file_path):
                logger.warning(f"Attachment not found, skipping: {file_path}")
                continue
            try:
                with open(file_path, "rb") as fil:
                    part = MIMEApplication(fil.read(), Name=os.path.basename(file_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                msg.attach(part)
                logger.info(f"Successfully prepared attachment: {os.path.basename(file_path)}")
            except Exception as e_attach:
                logger.error(f"Error attaching file {file_path}: {e_attach}", exc_info=True)
        
        logger.info(f"Attempting to send email via Brevo SMTP {final_smtp_server}:{final_smtp_port} from '{final_displayed_from_email}' (auth user: '{final_smtp_login}') to '{recipient_email}'")
        
        server = None 
        if final_smtp_port == 465: # SSL
            server = smtplib.SMTP_SSL(final_smtp_server, final_smtp_port, timeout=10)
        elif final_smtp_port == 587 or final_smtp_port == 2525: # TLS
            server = smtplib.SMTP(final_smtp_server, final_smtp_port, timeout=10)
            server.starttls() 
        else: 
            logger.error(f"Unsupported Brevo SMTP port configuration: {final_smtp_port}.")
            return False

        server.login(final_smtp_login, final_smtp_key) 
        server.sendmail(final_displayed_from_email, recipient_email, msg.as_string())
        server.quit()
        
        logger.info(f"Email successfully sent to {recipient_email} via Brevo with subject '{subject}'.")
        return True
        
    except smtplib.SMTPAuthenticationError as e_auth:
        logger.error(f"Brevo SMTP Authentication Error. Login: '{final_smtp_login}'. Key Used: '******'. Error: {e_auth}. Check credentials in config.py or environment variables.", exc_info=True)
        return False
    except smtplib.SMTPConnectError as e_conn:
        logger.error(f"Brevo SMTP Connection Error to {final_smtp_server}:{final_smtp_port}: {e_conn}.", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Failed to send email via Brevo: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger.info("Testing email_sender.py using settings from config.py (with potential fallback for key)...")
    
    if not config:
        logger.error("config.py could not be imported. Cannot run test with config values.")
    else:
        # Test recipient will also come from config or can be set here for testing
        test_recipient = getattr(config, "APP_EMAIL_RECIPIENT", "test_recipient@example.com")
        
        # These will be pulled from config by the function, but we log them for clarity
        test_smtp_login = getattr(config, "BREVO_SMTP_LOGIN", "config_login_missing")
        test_displayed_from = getattr(config, "BREVO_SENDER_DISPLAY_EMAIL", "config_display_email_missing")
        key_env_var_name = getattr(config, "BREVO_SMTP_KEY_ENV_VAR_NAME", "BREVO_SMTP_KEY")
        key_from_env = os.getenv(key_env_var_name)
        key_from_fallback = getattr(config, "BREVO_SMTP_KEY_FALLBACK_FOR_TESTING", None)

        logger.info(f"Test Recipient from config: {test_recipient}")
        logger.info(f"SMTP Login from config: {test_smtp_login}")
        logger.info(f"Displayed From Email from config: {test_displayed_from}")
        logger.info(f"SMTP Key will be resolved from env var '{key_env_var_name}' or fallback in config.")

        if not (key_from_env or key_from_fallback):
             logger.warning(f"Skipping direct Brevo email test: BREVO_SMTP_KEY ('{key_env_var_name}') environment variable not set AND no fallback key in config.py.")
        else:
            success = send_job_application_email(
                subject="Test Email - Sourced from config.py",
                body="This email was sent using settings defined in config.py.",
                recipient_email=test_recipient
                # The function will use its internal logic to get other params from config
            )
            if success:
                logger.info(f"Test Brevo email sent successfully to {test_recipient}.")
            else:
                logger.error(f"Test Brevo email failed to send to {test_recipient}.")