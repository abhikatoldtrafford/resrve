from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
from googleapiclient.discovery import build
import base64
import json
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import openai
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('email_system')

# Initialize OpenAI client at module level
openai_client = None

# Global constants
TEST_EMAIL = "abhikatoldtrafford@gmail.com"

# Global EmailSystem instance (singleton)
EMAIL_CLIENT = None

def init_openai_client(api_key):
    """Initialize the OpenAI client with the provided API key."""
    global openai_client
    if api_key:
        openai_client = openai.OpenAI(api_key=api_key)
        return True
    return False

def get_email_client(credentials_json):
    """Singleton pattern for email client to prevent multiple initializations"""
    global EMAIL_CLIENT
    if EMAIL_CLIENT is None:
        EMAIL_CLIENT = EmailSystem(credentials_json)
    return EMAIL_CLIENT

class EmailSystem:
    def __init__(self, credentials_json: str):
        """Initialize the Gmail API client with OAuth 2.0 authentication."""
        self.credentials = self.authenticate(credentials_json)
        self.service = build('gmail', 'v1', credentials=self.credentials)

    def authenticate(self, credentials_json):
        """Authenticate using OAuth 2.0 and save credentials to token.pickle."""
        creds = None
        token_path = "token.pickle"

        # Load existing credentials if available
        if os.path.exists(token_path):
            try:
                with open(token_path, "rb") as token:
                    creds = pickle.load(token)
                    logger.info("Loaded credentials from token.pickle")
            except Exception as e:
                logger.error(f"Error loading credentials: {str(e)}")

        # Refresh credentials or create a new login flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed expired credentials")
                except Exception as e:
                    logger.error(f"Error refreshing credentials: {str(e)}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_json, 
                        ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']
                    )
                    creds = flow.run_local_server(port=0)
                    logger.info("Created new credentials via OAuth flow")
                    
                    # Save new credentials
                    with open(token_path, "wb") as token:
                        pickle.dump(creds, token)
                except Exception as e:
                    logger.error(f"Error during OAuth flow: {str(e)}")
                    raise
        
        return creds

    def send_email(self, to: str, subject: str, body: str, html_body: str = None, from_email: str = "will@reserved.events") -> dict:
        """Send an email via Gmail API with optional HTML formatting."""
        try:
            # Validate the 'to' email address
            if not to or '@' not in to:
                logger.warning(f"Invalid recipient email address: {to}")
                return {"status": "error", "message": f"Invalid recipient email address: {to}"}
            
            # Create a multipart message if HTML is provided, otherwise use simple text
            if html_body:
                message = MIMEMultipart('alternative')
                message['To'] = to
                message['From'] = from_email
                message['Subject'] = subject
                
                # Attach plain text and HTML versions
                part1 = MIMEText(body, 'plain')
                part2 = MIMEText(html_body, 'html')
                message.attach(part1)
                message.attach(part2)
            else:
                message = EmailMessage()
                message['To'] = to
                message['From'] = from_email
                message['Subject'] = subject
                message.set_content(body)
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            sent_message = self.service.users().messages().send(
                userId='me', body={'raw': encoded_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {to}")
            return {"status": "sent", "message_id": sent_message['id'], "message": "Email sent successfully."}
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {"status": "error", "message": f"Failed to send email: {str(e)}"}

    def read_email(self, query: str) -> dict:
        """Read the latest email matching a specific query."""
        try:
            results = self.service.users().messages().list(userId='me', q=query, maxResults=1).execute()
            messages = results.get('messages', [])

            if not messages:
                logger.info(f"No emails found matching query: {query}")
                return {"status": "pending", "message": "No response received yet."}

            msg_data = self.service.users().messages().get(userId='me', id=messages[0]['id']).execute()
            snippet = msg_data.get('snippet', 'No content available.')
            logger.info(f"Found email matching query: {query}")
            return {"status": "received", "message": snippet}
        except Exception as e:
            logger.error(f"Failed to read email: {str(e)}")
            return {"status": "error", "message": f"Failed to read email: {str(e)}"}


class VenueReservationAgent:
    def __init__(self, credentials_json: str, openai_api_key: str = None):
        """Initialize the venue reservation agent with email and AI capabilities."""
        # Use the singleton email client
        self.email_system = get_email_client(credentials_json)
        
        # Initialize the OpenAI client
        global openai_client
        if openai_api_key and not openai_client:
            init_openai_client(openai_api_key)
        
        self.ai_available = openai_client is not None
        self.model = "gpt-4o"  # Default model
        
    def generate_email_content_with_ai(self, event_details: dict) -> tuple:
        """Generate email content using OpenAI to create a professional, well-formatted message."""
        global openai_client
        
        if not openai_client:
            logger.warning("OpenAI client not initialized. Falling back to template-based email.")
            return self.generate_email_content_template(event_details)
            
        try:
            # Get the venue name for subject line
            venue_name = event_details.get('venue_name', 'Selected Venue')
            event_date = event_details.get('start_date', 'TBD')
            display_start_time = event_details.get('display_start_time', event_details.get('event_time', ''))

            # Create dynamic subject line with the new format
            subject = f"Reservation Request: {venue_name} at {event_date} {display_start_time}"
            
            # Create a prompt that instructs the AI to generate a professional email
            prompt = f"""
            Create a professional, engaging email to inquire about venue reservation for a corporate event. 
            I am an AI agent emailing on behalf of Reserved.ai for this venue booking.
            
            The email should:
            - Start with "Dear Sir/Madam,"
            - Clearly state I am an AI agent emailing on behalf of Reserved.ai
            - Be concise, professional, and highlight key requirements
            - Use HTML formatting for the HTML version
            - End with "AI Agent\\nReserved.ai\\nsupport@reserved.events" signature
            
            Event details:
            - Event Name: {event_details.get('event_name', 'Corporate Event')}
            - Type: {event_details.get('event_type', 'N/A')}
            - Date: {event_details.get('start_date', 'TBD')}
            - Time: {event_details.get('display_start_time', '')} to {event_details.get('display_end_time', '')}
            - Location: {', '.join(event_details.get('locations', ['']))}
            - Number of Attendees: {event_details.get('attendees', 'N/A')}
            - Budget: ${event_details.get('venue_budget', 'Flexible')}
            - Food & Beverage: {event_details.get('food_beverage', 'N/A')}
            - Dietary Restrictions: {', '.join(event_details.get('dietary_restrictions', []))}
            - Private/Semi-Private: {event_details.get('private_preference', 'No preference')}
            - Neighborhood Preference: {event_details.get('neighborhood_preference', 'N/A')}
            - Atmosphere Desired: {event_details.get('atmosphere', 'N/A')}
            - Special Requirements: {event_details.get('special_requirements', 'N/A')}
            - Decision Deadline: {event_details.get('decision_date', 'N/A')}
            - Additional Notes: {event_details.get('notes', 'N/A')}
            
            Return TWO versions:
            1. A plain text email version (no HTML)
            2. An HTML formatted version with the same content but with professional styling
            
            For the HTML version, use styles to make it attractive but professional. Bold important details, use spacing for readability.
            
            Format your response as a JSON with these fields:
            {{"plain_text": "Plain text version", "html": "HTML version"}}
            """
            
            # Generate the email content using OpenAI
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            content = json.loads(response.choices[0].message.content)
            
            # Extract the components
            plain_text = content.get("plain_text", "")
            html = content.get("html", "")
            
            logger.info(f"Generated AI email with subject: {subject}")
            return subject, plain_text, html
            
        except Exception as e:
            logger.error(f"Error generating email with AI: {str(e)}")
            # Fall back to template method
            return self.generate_email_content_template(event_details)
    
    def generate_email_content_template(self, event_details: dict) -> tuple:
        """Generate email content using templates when AI is not available."""
        # Extract key information for the subject
        venue_name = event_details.get("venue_name", "Selected Venue")
        event_date = event_details.get("start_date", "")
        display_start_time = event_details.get("display_start_time", event_details.get("event_time", ""))
        
        # Create a personalized subject line with the requested format
        subject = f"Reservation Request: {venue_name} at {event_date} {display_start_time}"
        
        # Generate the plain text version
        plain_text = self._generate_plain_text(event_details)
        
        # Generate the HTML version
        html = self._generate_html(event_details)
        
        return subject, plain_text, html
    
    def _generate_plain_text(self, event_details: dict) -> str:
        """Generate plain text email body."""
        # Extract key details
        event_name = event_details.get("event_name", "Corporate Event")
        venue_name = event_details.get("venue_name", "Selected Venue")
        start_date = event_details.get("start_date", "")
        display_start_time = event_details.get("display_start_time", event_details.get("event_time", ""))
        display_end_time = event_details.get("display_end_time", event_details.get("event_endtime", ""))
        locations = ", ".join(event_details.get("locations", []))
        attendees = event_details.get("attendees", "")
        
        # Start building the email body with important details first
        body_parts = [
            f"Dear Sir/Madam,\n\nI am an AI agent emailing on behalf of Reserved.ai, helping to coordinate a venue reservation for our client.\n\n",
            f"I am inquiring about availability for the following event at {venue_name}:\n\n",
            f"EVENT DETAILS:",
            f"Name: {event_name}",
        ]
        
        # Add event type if provided and valid
        if event_details.get("event_type") and event_details.get("event_type") != "Select an event type":
            body_parts.append(f"Type: {event_details.get('event_type')}")
        
        # Add date and time information
        if start_date:
            body_parts.append(f"Date: {start_date}")
        
        # Add time information
        if display_start_time and display_end_time:
            body_parts.append(f"Time: {display_start_time} to {display_end_time}")
        elif display_start_time:
            body_parts.append(f"Time: {display_start_time}")
        
        # Add location if provided
        if locations:
            body_parts.append(f"Location Preference: {locations}")
        
        # Add attendees if provided
        if attendees:
            body_parts.append(f"Number of Attendees: {attendees}")
        
        # Optional fields with their conditions
        optional_fields = [
            ("Venue Type", "venue_type", lambda v: v and v != "Select a venue type"),
            ("Total Budget", "venue_budget", lambda v: v > 0, lambda v: f"${v}"),
            ("Food & Beverage", "food_beverage", lambda v: v and v != "Not needed"),
            ("Private/Semi-Private Preference", "private_preference", lambda v: bool(v)),
            ("Neighborhood Preference", "neighborhood_preference", lambda v: bool(v)),
            ("Desired Atmosphere", "atmosphere", lambda v: bool(v)),
            ("Special Requirements", "special_requirements", lambda v: bool(v)),
        ]
        
        # Add optional fields if they meet their condition
        for field_info in optional_fields:
            label = field_info[0]
            key = field_info[1]
            
            # Get the value from event details
            value = event_details.get(key)
            
            # Check if value exists and meets the condition
            if value is not None and field_info[2](value):
                # Apply formatter function if provided
                if len(field_info) > 3 and callable(field_info[3]):
                    value = field_info[3](value)
                body_parts.append(f"{label}: {value}")
        
        # Add dietary restrictions if applicable
        if event_details.get("dietary_restrictions"):
            restrictions = ", ".join(event_details.get("dietary_restrictions", []))
            body_parts.append(f"Dietary Restrictions: {restrictions}")
            
        # Add additional notes if provided
        if event_details.get("notes"):
            body_parts.append(f"\nAdditional Notes: {event_details.get('notes')}")
            
        # Add decision timeline
        if event_details.get("decision_date"):
            body_parts.append(f"\nWe need to make a decision by {event_details.get('decision_date')}.")
            
        # Close the email
        body_parts.append("\nCould you please confirm availability for this event and provide information about any suitable packages or options you offer?")
        body_parts.append("\nI look forward to your response and would be happy to discuss further details.")
        body_parts.append("\nThank you for your consideration.")
        body_parts.append("\nBest regards,")
        body_parts.append("AI Agent")
        body_parts.append("reserved.events")
        body_parts.append("support@reserved.events")
        
        # Join all parts with line breaks
        body = "\n".join(body_parts)
        
        return body

    def _generate_html(self, event_details: dict) -> str:
        """Generate HTML formatted email body."""
        # Extract key details
        event_name = event_details.get("event_name", "Corporate Event")
        venue_name = event_details.get("venue_name", "Selected Venue")
        start_date = event_details.get("start_date", "")
        display_start_time = event_details.get("display_start_time", event_details.get("event_time", ""))
        display_end_time = event_details.get("display_end_time", event_details.get("event_endtime", ""))
        locations = ", ".join(event_details.get("locations", []))
        attendees = event_details.get("attendees", "")
        
        # Start building the HTML email with styling
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<style>',
            'body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }',
            '.header { color: #4a6fa5; padding-bottom: 10px; border-bottom: 1px solid #eee; margin-bottom: 20px; }',
            '.section { margin-bottom: 20px; }',
            '.section-title { font-weight: bold; color: #4a6fa5; margin-bottom: 10px; }',
            '.detail-row { margin-bottom: 5px; }',
            '.label { font-weight: bold; width: 180px; display: inline-block; }',
            '.footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; font-size: 90%; color: #777; }',
            '.highlight { color: #e74c3c; font-weight: bold; }',
            '</style>',
            '</head>',
            '<body>',
            '<div class="header">',
            f'<h2>Venue Inquiry: {event_name} at {venue_name}</h2>',
            '</div>',
            '<div class="section">',
            '<p>Dear Sir/Madam,</p>',
            '<p>I am an AI agent emailing on behalf of <strong>Reserved.ai</strong>, helping to coordinate a venue reservation for our client.</p>',
            '<p>I am inquiring about availability for the following event:</p>',
            '</div>',
            '<div class="section">',
            '<div class="section-title">EVENT DETAILS</div>'
        ]
        
        # Add essential details
        html_parts.append('<div class="detail-row"><span class="label">Event Name:</span> <strong>' + event_name + '</strong></div>')
        
        if event_details.get("event_type") and event_details.get("event_type") != "Select an event type":
            html_parts.append('<div class="detail-row"><span class="label">Type:</span> ' + event_details.get("event_type") + '</div>')
        
        if start_date:
            html_parts.append('<div class="detail-row"><span class="label">Date:</span> <strong>' + start_date + '</strong></div>')
        
        if display_start_time and display_end_time:
            html_parts.append('<div class="detail-row"><span class="label">Time:</span> <strong>' + display_start_time + ' to ' + display_end_time + '</strong></div>')
        elif display_start_time:
            html_parts.append('<div class="detail-row"><span class="label">Time:</span> <strong>' + display_start_time + '</strong></div>')
        
        if locations:
            html_parts.append('<div class="detail-row"><span class="label">Location Preference:</span> ' + locations + '</div>')
        
        if attendees:
            html_parts.append('<div class="detail-row"><span class="label">Number of Attendees:</span> <strong>' + str(attendees) + '</strong></div>')
        
        # Optional fields
        optional_fields = [
            ("Venue Type", "venue_type", lambda v: v and v != "Select a venue type"),
            ("Total Budget", "venue_budget", lambda v: v > 0, lambda v: f"${v}"),
            ("Food & Beverage", "food_beverage", lambda v: v and v != "Not needed"),
            ("Private/Semi-Private", "private_preference", lambda v: bool(v)),
            ("Neighborhood Preference", "neighborhood_preference", lambda v: bool(v)),
            ("Desired Atmosphere", "atmosphere", lambda v: bool(v)),
            ("Special Requirements", "special_requirements", lambda v: bool(v)),
        ]
        
        # Add optional fields if they meet their condition
        for field_info in optional_fields:
            label = field_info[0]
            key = field_info[1]
            
            # Get the value from event details
            value = event_details.get(key)
            
            # Check if value exists and meets the condition
            if value is not None and field_info[2](value):
                # Apply formatter function if provided
                if len(field_info) > 3 and callable(field_info[3]):
                    value = field_info[3](value)
                html_parts.append(f'<div class="detail-row"><span class="label">{label}:</span> {value}</div>')
        
        # Add dietary restrictions
        if event_details.get("dietary_restrictions"):
            restrictions = ", ".join(event_details.get("dietary_restrictions", []))
            html_parts.append(f'<div class="detail-row"><span class="label">Dietary Restrictions:</span> {restrictions}</div>')
        
        html_parts.append('</div>')  # Close the event details section
        
        # Additional notes
        if event_details.get("notes"):
            html_parts.append('<div class="section">')
            html_parts.append('<div class="section-title">ADDITIONAL NOTES</div>')
            html_parts.append(f'<p>{event_details.get("notes")}</p>')
            html_parts.append('</div>')
            
        # Decision timeline
        if event_details.get("decision_date"):
            html_parts.append('<div class="section">')
            html_parts.append('<div class="section-title">TIMELINE</div>')
            html_parts.append(f'<p>We need to make a decision by <span class="highlight">{event_details.get("decision_date")}</span>.</p>')
            html_parts.append('</div>')
        
        # Closing
        html_parts.append('<div class="section">')
        html_parts.append('<p>Could you please confirm availability for this event and provide information about any suitable packages or options you offer?</p>')
        html_parts.append('<p>I look forward to your response and would be happy to discuss further details.</p>')
        html_parts.append('</div>')
        
        # Footer
        html_parts.append('<div class="footer">')
        html_parts.append('<p>Thank you for your consideration.</p>')
        html_parts.append('<p>Best regards,<br>AI Agent<br>Reserved.ai<br>support@reserved.events</p>')
        html_parts.append('</div>')
        
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        return '\n'.join(html_parts)

    def book_venue(self, venue_email: str, event_details: dict) -> dict:
        """Send a venue reservation request via email using event details from the form."""
        # Validate email address before sending
        if not venue_email or '@' not in venue_email:
            logger.warning(f"Invalid venue email address: {venue_email}")
            return {"status": "error", "message": f"Invalid venue email address: {venue_email}"}
        
        # Generate email content with AI if available, otherwise use template
        if self.ai_available:
            subject, plain_text, html = self.generate_email_content_with_ai(event_details)
        else:
            subject, plain_text, html = self.generate_email_content_template(event_details)
            
        logger.info(f"Sending venue request to {venue_email}")
        return self.email_system.send_email(venue_email, subject, plain_text, html)

    def check_status(self, venue_email: str, event_name: str, date: str = None) -> dict:
        """Check reservation status by analyzing email responses with GPT."""
        global openai_client
        
        if not openai_client:
            logger.warning("OpenAI client not initialized. Cannot analyze email responses.")
            return {"status": "unknown", "message": "AI analysis unavailable. Please check email manually."}
            
        query = f"from:{venue_email} subject:{event_name}"
        if date:
            query += f" {date}"
            
        logger.info(f"Checking status for emails from {venue_email} about {event_name}")
        email_response = self.email_system.read_email(query)

        if email_response["status"] == "error":
            return email_response
        
        if email_response["status"] == "pending":
            return email_response
        
        # Use GPT to analyze the email response
        prompt = f"""
        Extract the venue reservation status from the following email response:
        {email_response["message"]}
        
        Format response as JSON with fields: 
        - status (confirmed/pending/declined)
        - message (a brief summary of the response)
        - next_steps (what should be done next based on this response)
        """
        
        try:
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"AI analysis complete: {result['status']}")
        except Exception as e:
            logger.error(f"Error analyzing email with AI: {str(e)}")
            result = {"status": "unknown", "message": f"{email_response['message']} (Error: {str(e)})"}

        return result


# Function to send email directly from main application
def send_venue_request(credentials_path, venue_email, event_details, openai_api_key=None, use_test_email=True):
    """Helper function to send a venue request email without creating separate instances."""
    try:
        # Use test email in development/testing mode
        if use_test_email:
            venue_email = TEST_EMAIL
            
        # Initialize OpenAI client if API key is provided
        if openai_api_key:
            init_openai_client(openai_api_key)
            
        # Use singleton pattern for agent
        agent = VenueReservationAgent(credentials_path, openai_api_key)
        return agent.book_venue(venue_email, event_details)
    except Exception as e:
        logger.error(f"Error sending venue request: {str(e)}")
        return {"status": "error", "message": str(e)}


# Function to check response status
def check_venue_response(credentials_path, venue_email, event_name, date=None, openai_api_key=None):
    """Helper function to check venue response status."""
    try:
        # Initialize OpenAI client if API key is provided
        if openai_api_key:
            init_openai_client(openai_api_key)
            
        # Use singleton pattern for agent
        agent = VenueReservationAgent(credentials_path, openai_api_key)
        return agent.check_status(venue_email, event_name, date)
    except Exception as e:
        logger.error(f"Error checking venue response: {str(e)}")
        return {"status": "error", "message": f"Error checking venue response: {str(e)}"}


def main():
    """Test function to demonstrate the email system functionality."""
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    
    # Test credentials path - replace with your actual credentials file path
    credentials_path = "client_secret.json"
    
    # Test event details based on the Streamlit form structure
    test_event_details = {
        "event_name": "Team Dinner in NYC",
        "venue_name": "Test Restaurant",  # Added venue name for subject line
        "venue_type": "Restaurants",
        "start_date": "03/20/2025",
        "event_type": "Dinner",
        "display_start_time": "6:00 PM",
        "display_end_time": "9:00 PM",
        "event_time": "18:00",
        "event_endtime": "21:00",
        "locations": ["New York"],
        "venue_budget": 5000,
        "attendees": 30,
        "food_beverage": "Full dinner service with wine pairing",
        "dietary_restrictions": ["Vegetarian", "Gluten-Free"],
        "special_requirements": "Private dining room with AV for brief presentation",
        "decision_date": "03/01/2025",
        "notes": "Would prefer restaurants in Manhattan, preferably midtown or downtown",
        "private_preference": "Private Only",
        "neighborhood_preference": "Midtown or Financial District",
        "atmosphere": "Upscale but not stuffy, modern decor"
    }
    
    # Test venue email - use the global test email
    test_venue_email = TEST_EMAIL
    
    print("\n===== EMAIL SYSTEM TEST =====\n")
    
    # Check if credentials file exists
    if not os.path.exists(credentials_path):
        print(f"Error: Credentials file not found at {credentials_path}")
        print("Please update the credentials_path variable with your actual Google API credentials file path.")
        return
    
    # Check if OpenAI API key is available
    if not openai_api_key:
        print("Warning: OpenAI API key not found in environment variables.")
        print("Email will be generated using templates instead of AI.")
    
    print("Sending test email...")
    result = send_venue_request(credentials_path, test_venue_email, test_event_details, openai_api_key)
    
    if result["status"] == "sent":
        print(f"Success! Email sent successfully. Message ID: {result.get('message_id')}")
    else:
        print(f"Error: {result.get('message')}")
    
    print("\nTo use this module in your application:")
    print("1. Import the needed functions:")
    print("   from email import send_venue_request, check_venue_response, init_openai_client")
    print("2. Initialize OpenAI client once at the start of your application:")
    print("   init_openai_client(openai_api_key)")
    print("3. Call send_venue_request() with your credentials and event details")
    print("4. Call check_venue_response() to check for venue responses")


if __name__ == "__main__":
    main()