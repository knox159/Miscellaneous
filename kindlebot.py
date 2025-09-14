import os
import subprocess
from telegram import Update, Document
from telegram.ext import filters
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler
from email.message import EmailMessage
import smtplib
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

BOT_TOKEN = "" #Insert Telegram bot token
# List of Kindle email addresses to send to
KINDLE_EMAILS = [
]
SENDER_EMAIL = "" #Email To send from
SENDER_PASSWORD = ""  # Replace this with your 16-character App Password from Google
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def convert_to_kindle_format(input_path):
    output_path = input_path.rsplit('.', 1)[0] + '.epub'
    try:
        subprocess.run(['ebook-convert', input_path, output_path, '--output-profile=kindle', '--prefer-metadata-cover'], check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        raise Exception(f"Conversion failed: {e}")

def send_to_kindle(file_path, kindle_emails=KINDLE_EMAILS, from_email=SENDER_EMAIL, 
                  smtp_server=SMTP_SERVER, smtp_port=SMTP_PORT, password=SENDER_PASSWORD):
    results = []
    
    # Create base message
    msg = MIMEMultipart()
    msg['Subject'] = 'New book for your Kindle'
    msg["From"] = from_email
    
    # Attach the book file
    with open(file_path, 'rb') as f:
        part = MIMEApplication(f.read(), _subtype="epub+zip")
        part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(file_path))
        msg.attach(part)

    # Connect to SMTP server once for all emails
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(from_email, password)
            
            # Send to each Kindle email
            for kindle_email in kindle_emails:
                try:
                    msg_copy = MIMEMultipart()
                    msg_copy['Subject'] = msg['Subject']
                    msg_copy['From'] = msg['From']
                    msg_copy['To'] = kindle_email
                    
                    # Copy the attachment
                    for part in msg.get_payload():
                        msg_copy.attach(part)
                    
                    smtp.send_message(msg_copy)
                    results.append((kindle_email, True, None))
                    print(f"Email sent successfully to {kindle_email}")
                except Exception as e:
                    results.append((kindle_email, False, str(e)))
                    print(f"Failed to send email to {kindle_email}: {e}")
        
        # If at least one email was sent successfully
        if any(success for _, success, _ in results):
            return results
        # If all emails failed
        raise Exception("Failed to send to all recipients")
    except Exception as e:
        print(f"SMTP connection failed: {e}")
        raise


# --- HANDLER ---
async def handle_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document
    
    if not is_supported_format(doc.file_name):
        await update.message.reply_text("❌ Unsupported file format. Please send an ebook file (.epub, .mobi, .pdf, .txt, .doc, or .docx)")
        return
        
    file_path = f"./{doc.file_name}"
    file = await doc.get_file()
    await file.download_to_drive(file_path)

    try:
        if doc.file_name.lower().endswith('.epub'):
            # If already in EPUB format, send directly
            await update.message.reply_text("📧 Sending to your Kindles...")
            results = send_to_kindle(file_path)
        else:
            # Convert to EPUB format first
            await update.message.reply_text("📚 Converting your book to EPUB format...")
            kindle_path = convert_to_kindle_format(file_path)
            
            await update.message.reply_text("📧 Sending to your Kindles...")
            results = send_to_kindle(kindle_path)
            
            # Clean up the converted file
            if os.path.exists(kindle_path):
                os.remove(kindle_path)
        
        # Report results for each recipient
        status_messages = []
        for email, success, error in results:
            if success:
                status_messages.append(f"✅ Sent to {email}")
            else:
                status_messages.append(f"❌ Failed to send to {email}: {error}")
        
        await update.message.reply_text("\n".join([f"📚 '{doc.file_name}'"] + status_messages))
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to process: {e}")
    finally:
        # Clean up the original file
        if os.path.exists(file_path):
            os.remove(file_path)

# --- MAIN ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
# Accept common ebook formats
def is_supported_format(file_name: str) -> bool:
    supported_formats = [".epub", ".mobi", ".pdf", ".txt", ".doc", ".docx"]
    return any(file_name.lower().endswith(fmt) for fmt in supported_formats)

# Handler for all documents
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        return
    
    if is_supported_format(update.message.document.file_name):
        await handle_book(update, context)
    else:
        await update.message.reply_text(
            "❌ Unsupported file format. Please send an ebook file (.epub, .mobi, .pdf, .txt, .doc, or .docx)"
        )

app.add_handler(MessageHandler(
    filters.Document.ALL,
    handle_document
))

app.run_polling()
