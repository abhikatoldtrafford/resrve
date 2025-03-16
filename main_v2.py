import streamlit as st
import json
from datetime import datetime
import pandas as pd
import urllib.parse
import time

# Import backend functions
from app import find_best_restaurants, get_venue_recommendation
from email_module import send_venue_request

# Page configuration
st.set_page_config(
    page_title="Venue Finder", 
    page_icon="🍽️", 
    layout="wide"
)

# Custom CSS for a modern, professional look
st.markdown("""
<style>
    /* Global styles */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Header styling */
    h1, h2, h3, h4, h5 {
        color: #2c3e50;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    h2 {
        font-size: 1.8rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .subtitle {
        font-size: 1.2rem;
        color: #6c757d;
        margin-top: 0;
        margin-bottom: 2rem;
    }
    
    /* Form styling */
    div[data-testid="stForm"] {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    /* Section headers */
    div[data-testid="stForm"] h3 {
        color: #3b82f6;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 10px;
        margin-top: 20px;
        margin-bottom: 15px;
    }
    
    /* Venue card styling */
    .venue-card {
        background-color: white;
        border-radius: 10px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
        border-left: 4px solid transparent;
    }
    .venue-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 15px rgba(0,0,0,0.1);
    }
    .venue-card h3 {
        color: #2c3e50;
        margin-top: 0;
        margin-bottom: 10px;
    }
    .score-badge {
        background-color: #3b82f6;
        color: white;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .selected-venue {
        border-left: 4px solid #3b82f6;
        background-color: #f0f7ff;
    }
    
    /* Button styling */
    .stButton button {
        font-weight: 500;
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    .stButton button:hover:not([disabled]) {
        transform: translateY(-2px);
    }
    
    /* Success and info messages */
    div[data-baseweb="notification"] {
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    
    /* Expander styling */
    details {
        background-color: white;
        border-radius: 8px;
        margin-bottom: 10px;
        border: 1px solid #e5e7eb;
    }
    details summary {
        padding: 10px 15px;
        font-weight: 500;
    }
    details > div:first-child {
        padding: 5px 20px 20px 20px;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #fff;
        box-shadow: 2px 0 10px rgba(0,0,0,0.05);
    }
    section[data-testid="stSidebar"] h2 {
        color: #3b82f6;
        margin-top: 20px;
    }
    
    /* Spinner styling */
    div[role="progressbar"] {
        color: #3b82f6 !important;
    }
    
    /* Location map container */
    .map-container {
        width: 100%;
        height: 200px;
        border: 1px solid #ddd;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        background: #f8f9fa;
        overflow: hidden;
    }
    .map-container a {
        color: #3b82f6;
        text-decoration: none;
        font-weight: 500;
    }
    .map-container a:hover {
        text-decoration: underline;
    }
    
    /* Time picker styling */
    .time-picker {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 10px;
        margin-bottom: 15px;
    }
    .time-picker-label {
        font-weight: 600;
        margin-bottom: 5px;
    }
    .time-picker-selects {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Tips section in sidebar */
    .tips-section h3 {
        color: #3b82f6;
        font-size: 1.2rem;
        margin: 20px 0 10px 0;
    }
    .tips-section ul {
        padding-left: 20px;
    }
    .tips-section li {
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'page' not in st.session_state:
    st.session_state.page = 'search'
if 'search_submitted' not in st.session_state:
    st.session_state.search_submitted = False
if 'event_details' not in st.session_state:
    st.session_state.event_details = {}
if 'recommended_venues' not in st.session_state:
    st.session_state.recommended_venues = []
if 'selection_reasoning' not in st.session_state:
    st.session_state.selection_reasoning = ""
if 'selected_venues' not in st.session_state:
    st.session_state.selected_venues = []
if 'emails_sent' not in st.session_state:
    st.session_state.emails_sent = {}
if 'venue_recommendations' not in st.session_state:
    st.session_state.venue_recommendations = {}
if 'loading_recommendations' not in st.session_state:
    st.session_state.loading_recommendations = set()
if 'progress_tracking' not in st.session_state:
    st.session_state.progress_tracking = {
        'recommendation_progress': 0,
        'email_progress': {'total': 0, 'current': 0}
    }
if 'shortlist_submitted' not in st.session_state:
    st.session_state.shortlist_submitted = False

# Function to change page
def change_page(page_name):
    st.session_state.page = page_name
    # Scroll to top when changing pages
    js = '''
    <script>
        window.parent.scrollTo(0, 0);
    </script>
    '''
    st.markdown(js, unsafe_allow_html=True)

# Callback functions to handle state changes
def handle_search_submit():
    st.session_state.search_submitted = True

def handle_shortlist_submit():
    st.session_state.shortlist_submitted = True
    # Change page and ensure we start at the top
    change_page('shortlist')

def toggle_venue_selection(venue, selected):
    """Handle venue selection/deselection with a maximum of 5 selections"""
    venue_names = [v.get('name') for v in st.session_state.selected_venues]
    
    if selected:
        # Add venue if not already in list and under 5 selections
        if venue.get('name') not in venue_names and len(venue_names) < 5:
            st.session_state.selected_venues.append(venue)
    else:
        # Remove venue if in list
        st.session_state.selected_venues = [
            v for v in st.session_state.selected_venues 
            if v.get('name') != venue.get('name')
        ]

# Function to load restaurant data for contact info
@st.cache_data
def load_restaurant_data(csv_path="cleaned_restaurants.csv"):
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
        return df
    except Exception as e:
        st.error(f"Error loading restaurant data: {str(e)}")
        return None

def reset_search():
    """Reset search state to allow a new search"""
    st.session_state.search_submitted = False
    st.session_state.recommended_venues = []
    st.session_state.selection_reasoning = ""
    st.session_state.selected_venues = []
    st.session_state.emails_sent = {}
    st.session_state.venue_recommendations = {}
    st.session_state.loading_recommendations = set()
    st.session_state.progress_tracking = {
        'recommendation_progress': 0,
        'email_progress': {'total': 0, 'current': 0}
    }
    st.session_state.shortlist_submitted = False

# Cache UI components
@st.cache_data(ttl=3600)
def get_sidebar_components():
    return {
        "sidebar_help": """
        <div class="tips-section">
            <h3>Enhanced AI Venue Finder</h3>
            <ol>
                <li><strong>Analyze Requirements</strong>: AI analyzes your event needs</li>
                <li><strong>Recommend Venues</strong>: Get detailed venue recommendations</li>
                <li><strong>Contact Venues</strong>: Reach out to selected venues directly</li>
            </ol>
            
            <h3>Tips</h3>
            <ul>
                <li>Be specific about your requirements</li>
                <li>Select up to 5 venues to contact</li>
                <li>Review venue details before sending inquiries</li>
            </ul>
        </div>
        """,
        "sidebar_contact": """
        <div style="padding: 10px 0;">
            <p>Contact our event specialists:</p>
            <p>📧 <a href="mailto:support@venuefinder.com">support@venuefinder.com</a></p>
            <p>📱 (555) 123-4567</p>
        </div>
        """
    }

@st.cache_data
def render_venue_card(venue_name, venue_address, venue_cuisine, venue_pricing, score, selected=False):
    """Cached venue card rendering"""
    # Normalize score
    display_score = round(score * 10, 1) if score <= 1 else round(score, 1)
    
    # Add selected class if venue is selected
    card_class = "venue-card selected-venue" if selected else "venue-card"
    
    return f"""
    <div class="{card_class}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3>{venue_name}</h3>
            <span class="score-badge">{display_score}/10 Match</span>
        </div>
        <p>
        📍 {venue_address} | 
        🍽️ {venue_cuisine} | 
        💰 {venue_pricing}
        </p>
    </div>
    """

def load_recommendations(event_details):
    """Load recommendations with progress indicator"""
    progress_placeholder = st.empty()
    status_text = st.empty()
    
    with progress_placeholder.container():
        progress_bar = st.progress(0)
        
        # Simulated progress before actual API call
        for i in range(5):
            progress = int((i + 1) / 15 * 100)
            progress_bar.progress(progress)
            status_text.text(f"Analyzing event requirements ({i+1}/5)...")
            time.sleep(0.3)
        
        for i in range(5, 15):
            progress = int((i + 1) / 15 * 100)
            progress_bar.progress(progress)
            status_text.text(f"Finding venue match {i-4}/10...")
            time.sleep(0.2)
        
        # Actual API call
        stage1_results = find_best_restaurants(event_details)
        
        # Complete the progress
        progress_bar.progress(100)
        status_text.text("Recommendations complete!")
        time.sleep(0.5)
    
    # Clear the progress indicators when done
    progress_placeholder.empty()
    status_text.empty()
    
    return stage1_results

def send_all_emails(venues, contact_details):
    """Send emails with progress tracking"""
    total = len(venues)
    st.session_state.progress_tracking['email_progress'] = {'total': total, 'current': 0}
    
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        success_count = 0
        
        for idx, venue in enumerate(venues):
            name = venue.get('name', 'Unnamed Venue')
            status_text.text(f"Sending inquiry to {name}...")
            
            # Add venue name to contact details for subject line
            venue_contact_details = contact_details.copy()
            venue_contact_details["venue_name"] = name
            
            # Update progress
            current = idx + 1
            progress = int(current / total * 100)
            progress_bar.progress(progress)
            st.session_state.progress_tracking['email_progress']['current'] = current
            
            # Use test email for all venues
            venue_email = "abhikatoldtrafford@gmail.com"
            
            try:
                result = send_venue_request(
                    "credentials.json", 
                    venue_email,
                    venue_contact_details,
                    st.secrets.get("OPENAI_API_KEY", None)
                )
                
                if result.get("status") == "sent":
                    st.session_state.emails_sent[name] = True
                    success_count += 1
                    time.sleep(0.5)  # Small delay for visual feedback
                else:
                    st.error(f"Failed to send to {name}: {result.get('message')}")
            except Exception as e:
                st.error(f"Error sending to {name}: {str(e)}")
    
        # Show completion message
        if success_count > 0:
            status_text.success(f"Successfully sent {success_count} inquiries!")
        else:
            status_text.error("Failed to send any inquiries. Please try again.")
        
        time.sleep(2)  # Show the message briefly
    
    return success_count

def create_time_picker(label, key_prefix):
    """Create a custom time picker with hour, minute and period selectors"""
    st.markdown(f"<div class='time-picker-label'>{label}</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        hour = st.selectbox("Hour", list(range(1, 13)), key=f"{key_prefix}_hour")
    with col2:
        minute = st.selectbox("Minute", ["00", "15", "30", "45"], key=f"{key_prefix}_minute")
    with col3:
        period = st.selectbox("AM/PM", ["AM", "PM"], key=f"{key_prefix}_period")
    
    # Convert to 24-hour format for internal use
    hour_24 = hour if period == "AM" and hour != 12 else hour + 12 if period == "PM" and hour != 12 else 0 if period == "AM" and hour == 12 else 12
    
    # Format for display (12-hour format)
    formatted_time = f"{hour}:{minute} {period}"
    
    # Format for database (24-hour format)
    military_time = f"{hour_24:02d}:{minute}"
    
    return formatted_time, military_time

def search_page():
    st.title("🍽️ Venue Finder")
    st.markdown("<p class='subtitle'>Discover the Perfect Venue for Your Corporate Event</p>", unsafe_allow_html=True)

    # Event Details Form
    with st.form("event_form", clear_on_submit=False):
        # Basic Event Information
        st.markdown("### Event Basics")
        event_name = st.text_input("Event Name *", value="Your Org's NYC dinner")
        col1, col2 = st.columns(2)
        with col1:
            venue_type = st.selectbox("Venue Type *", 
                ["Select a venue type", "Restaurants", "Bars (coming soon)", "Event Spaces (Coming Soon)"])
            
        with col2:
            event_type = st.selectbox("Event Type *", 
                ["Select an event type", "Breakfast", "Lunch", "Dinner", "Happy Hour (coming soon)", "Experience (coming soon)"])
        start_date = st.date_input("Event Date *")
        
        # Improved time picker
        st.markdown("### Event Time")
        time_col1, time_col2 = st.columns(2)
        
        with time_col1:
            display_start_time, event_time = create_time_picker("Start Time", "start")
            
        with time_col2:
            display_end_time, event_endtime = create_time_picker("End Time", "end")
        
        # Location and Proximity
        st.markdown("### Location Details")
        locations = st.multiselect(
            "Event City", 
            ["San Francisco", "New York", "Chicago", "Boston", "Seattle"],
            max_selections=1
        )
        
        address_proximity = st.text_input(
            "(Optional) Address near preferred venue (within 0.50 miles)",
            help="Enter a specific address to find nearby venues"
        )
        neighborhood_preference = st.text_input(
            "(Optional) Preferred Neighborhood",
            help="Specify a desired neighborhood for your venue"
        )
        
        # Venue Preferences
        st.markdown("### Venue Preferences")
        atmosphere = st.text_area(
            "Desired Venue Atmosphere",
            placeholder="e.g., Modern, Trendy, Cozy, Elegant, Women-Owned, BIPOC-Owned",
            help="Describe the vibe you're looking for"
        )
        
        private_preference = st.radio(
            "Private vs Semi-Private Dining Preference",
            ["Private Only", "Semi-Private Only", "No preference (see both options)"]
        )
        
        # Event Specifics
        st.markdown("### Event Specifics")
        col3, col4 = st.columns(2)
        with col3:
            venue_budget = st.number_input("Total Event Budget ($) *", min_value=0, value=10000)
        with col4:
            attendees = st.number_input("Number of Attendees *", min_value=1, max_value=500, value=80)
        
        # Food & Beverage
        st.markdown("### Food & Beverage")
        fb_needed = st.checkbox("Food & Beverage Required", value=True)
        fb_details = st.text_input(
            "F&B Details",
            value="Light bites and drinks, standing reception",
            disabled=not fb_needed
        )
        
        # Dietary Requirements
        dietary_restrictions_needed = st.radio(
            "Dietary Restrictions?", 
            ["Yes", "No"], 
            horizontal=True
        )
        if dietary_restrictions_needed == "Yes":
            dietary_restrictions = st.multiselect(
                "Select Dietary Restrictions",
                ["Vegetarian", "Vegan", "Kosher", "Halal", "Gluten-Free", "Other"]
            )
        else:
            dietary_restrictions = []
        
        # Additional Details
        st.markdown("### Additional Information")
        special_requirements = st.text_area(
            "Special Requirements",
            placeholder="AV equipment, custom menus, accessibility needs, etc."
        )
        
        decision_date = st.date_input("Decision Date *")
        notes = st.text_area(
            "Additional Notes", 
            value="Date flexibility, open to sharing rooms"
        )
        
        # Submit Button - using callback to update session state
        submitted = st.form_submit_button("Find Venues", type="primary", on_click=handle_search_submit)

        # Prepare comprehensive event details dictionary when form is submitted
        if submitted:
            st.session_state.event_details = {
                "event_name": event_name,
                "venue_type": venue_type,
                "start_date": start_date.strftime("%m/%d/%Y"),
                "event_type": event_type,
                "event_time": event_time,
                "event_endtime": event_endtime,
                "display_start_time": display_start_time,
                "display_end_time": display_end_time,
                "locations": locations,
                "venue_budget": venue_budget,
                "attendees": attendees,
                "food_beverage": fb_details if fb_needed else "Not needed",
                "dietary_restrictions": dietary_restrictions,
                "special_requirements": special_requirements,
                "decision_date": decision_date.strftime("%m/%d/%Y"),
                "notes": notes,
                "private_preference": private_preference,
                "address_proximity": address_proximity,
                "neighborhood_preference": neighborhood_preference,
                "atmosphere": atmosphere
            }

    # Process search after form is submitted (outside the form)
    if st.session_state.search_submitted and len(st.session_state.recommended_venues) == 0:
        # Show spinner while loading recommendations
        with st.spinner("Finding perfect venues for your event..."):
            # Get event details from session state
            event_details = st.session_state.event_details
            
            # Use improved loading function with progress bar
            stage1_results = load_recommendations(event_details)
            
            # Store results in session state
            if stage1_results and "top_restaurants" in stage1_results:
                st.session_state.recommended_venues = stage1_results["top_restaurants"]
                if "selection_reasoning" in stage1_results:
                    st.session_state.selection_reasoning = stage1_results["selection_reasoning"]
            else:
                st.error("No venues found. Please adjust your search criteria.")
                reset_search()
    
    # Display Results
    if st.session_state.search_submitted and st.session_state.recommended_venues:
        venues = st.session_state.recommended_venues
        
        st.markdown("## Top Venue Recommendations")
        st.markdown("<p style='margin-bottom:20px;'>Select up to 5 venues you'd like to contact. Our AI has found these venues based on your requirements.</p>", unsafe_allow_html=True)
        
        # Create columns for venues with checkboxes
        for idx, venue in enumerate(venues, 1):
            venue_name = venue.get('name', f'Venue {idx}')
            
            # Check if this venue is in selected venues
            selected = venue_name in [v.get('name') for v in st.session_state.selected_venues]
            
            with st.container():
                col1, col2 = st.columns([0.1, 0.9])
                
                with col1:
                    # Add checkbox for selection with unique key
                    checkbox_value = st.checkbox(
                        f"Select", 
                        key=f"select_{venue_name}_{idx}",
                        value=selected
                    )
                    
                    # Update selection in session state if checkbox value changes
                    if checkbox_value != selected:
                        toggle_venue_selection(venue, checkbox_value)
                
                with col2:
                    # Handle potential missing data
                    name = venue.get('name', 'Unnamed Venue')
                    address = venue.get('address', 'Address not available')
                    cuisine = venue.get('cuisine', 'Various Cuisine')
                    pricing = venue.get('pricing', 'Not specified')
                    score = venue.get('score', 0)
                    
                    # Use cached venue card renderer
                    card_html = render_venue_card(name, address, cuisine, pricing, score, selected)
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    # Expandable section for detailed recommendation
                    with st.expander(f"Detailed Recommendation for {name}"):
                        # Use a unique key for the recommendation based on venue name
                        rec_key = f"rec_{venue_name}_{idx}"
                        
                        # Check if recommendation is being loaded
                        if rec_key in st.session_state.loading_recommendations:
                            st.write("Loading recommendation...")
                            progress_bar = st.progress(0)
                            for i in range(100):
                                time.sleep(0.01)
                                progress_bar.progress(i + 1)
                            # After progress completes, set loading to False and fetch the recommendation
                            st.session_state.loading_recommendations.remove(rec_key)
                            recommendation = get_venue_recommendation(venue, st.session_state.event_details, idx)
                            st.session_state.venue_recommendations[rec_key] = recommendation
                        
                        # Check if recommendation exists, otherwise start loading
                        elif rec_key not in st.session_state.venue_recommendations:
                            st.session_state.loading_recommendations.add(rec_key)
                            st.rerun()
                        
                        # Display the cached recommendation
                        st.write(st.session_state.venue_recommendations[rec_key])
        
        # Display selection count and shortlist button
        selected_count = len(st.session_state.selected_venues)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            # Selection feedback
            if selected_count > 5:
                st.error(f"You've selected {selected_count} venues. Please limit your selection to 5.")
            elif selected_count > 0:
                st.success(f"You've selected {selected_count} venue(s)")
                st.button("Form Shortlist ➡️", type="primary", key="form_shortlist", 
                          help="Continue to the next step with your selected venues",
                          on_click=handle_shortlist_submit)
            else:
                st.info("Select at least one venue to form a shortlist")
        
        # Optional reasoning display
        if st.session_state.selection_reasoning:
            with st.expander("Why these venues?"):
                st.write(st.session_state.selection_reasoning)
        
        # Reset button to start new search
        if st.button("Start New Search"):
            reset_search()
            st.rerun()

    # Sidebar with help and information
    with st.sidebar:
        st.header("🤔 How It Works")
        sidebar_components = get_sidebar_components()
        st.markdown(sidebar_components["sidebar_help"], unsafe_allow_html=True)

        st.divider()
        st.header("📞 Need Help?")
        st.markdown(sidebar_components["sidebar_contact"], unsafe_allow_html=True)

def shortlist_page():
    st.title("🍽️ Your Venue Shortlist")
    st.markdown("<p class='subtitle'>Review and Contact Your Selected Venues</p>", unsafe_allow_html=True)
    
    # Button to go back to search
    if st.button("⬅️ Back to Search Results"):
        change_page('search')
        st.rerun()
    
    # Get selected venues and event details
    selected_venues = st.session_state.selected_venues
    event_details = st.session_state.event_details
    
    # Check if there are selected venues
    if not selected_venues:
        st.warning("No venues selected. Please go back and select venues.")
        return
    
    # Load restaurant data to get contact info
    df = load_restaurant_data()
    
    # User contact information
    st.markdown("### Your Contact Information")
    col1, col2 = st.columns(2)
    with col1:
        user_name = st.text_input("Your Full Name *")
        user_email = st.text_input("Your Email Address *")
    with col2:
        user_phone = st.text_input("Your Phone Number")
        user_company = st.text_input("Company Name")
    
    # Display selected venues with contact information
    st.markdown("## Selected Venues")
    
    for idx, venue in enumerate(selected_venues, 1):
        with st.container():
            st.markdown(f"""<div class="venue-card">""", unsafe_allow_html=True)
            
            col1, col2 = st.columns([0.7, 0.3])
            
            with col1:
                # Extract venue information
                venue_id = venue.get('id', -1)
                name = venue.get('name', 'Unnamed Venue')
                address = venue.get('address', 'Address not available')
                cuisine = venue.get('cuisine', 'Various Cuisine')
                
                # Try to get contact info from CSV
                venue_email = None
                venue_phone = None
                venue_website = None
                
                if df is not None:
                    try:
                        # Try to find matching restaurant by name
                        matching_rows = df[df['Restaurant name'] == name]
                        if not matching_rows.empty:
                            venue_row = matching_rows.iloc[0]
                            venue_email = None if pd.isna(venue_row.get('Email Address')) else venue_row.get('Email Address')
                            venue_phone = None if pd.isna(venue_row.get('Phone #:')) else venue_row.get('Phone #:')
                            venue_website = None if pd.isna(venue_row.get('Restaurant website')) else venue_row.get('Restaurant website')
                        elif venue_id >= 0 and venue_id < len(df):
                            # Fallback to id
                            venue_row = df.iloc[venue_id]
                            venue_email = None if pd.isna(venue_row.get('Email Address')) else venue_row.get('Email Address')
                            venue_phone = None if pd.isna(venue_row.get('Phone #:')) else venue_row.get('Phone #:')
                            venue_website = None if pd.isna(venue_row.get('Restaurant website')) else venue_row.get('Restaurant website')
                    except Exception as e:
                        st.error(f"Error getting contact info: {e}")
                
                # Display venue details
                st.markdown(f"### {idx}. {name}")
                st.markdown(f"**Address:** {address}")
                st.markdown(f"**Cuisine:** {cuisine}")
                
                if venue_phone:
                    st.markdown(f"**Phone:** {venue_phone}")
                
                if venue_website:
                    st.markdown(f"**Website:** [{venue_website}]({venue_website})")
                
                # Email field (editable if not found)
                venue_key = f"email_{name}_{idx}"
                if venue_email:
                    st.markdown(f"**Email:** {venue_email}")
                    # Store in session state for sending
                    if venue_key not in st.session_state:
                        st.session_state[venue_key] = venue_email
                else:
                    venue_email = st.text_input(f"Email for {name} *", key=venue_key)
                
                # Show if email has been sent
                email_status = st.session_state.emails_sent.get(name, False)
                if email_status:
                    st.markdown("✅ **Inquiry Sent**")
            
            with col2:
                # Map display based on address
                st.markdown("#### Location")
                
                # Get address for map
                map_address = address
                if not map_address or map_address == "Address not available":
                    # Try to get address from CSV
                    if df is not None and venue_id >= 0:
                        try:
                            map_address = df.iloc[venue_id].get('Physical Address', "")
                        except:
                            pass
                
                # Create a Google Maps embed if we have an address
                if map_address and map_address != "Address not available":
                    # URL encode the address for the Google Maps embed
                    encoded_address = urllib.parse.quote(map_address)
                    search_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
                    
                    st.markdown(f"""
                    <div class="map-container">
                        <div>
                            <p style="margin:0;padding:0;">{map_address}</p>
                            <a href="{search_url}" target="_blank">View on Google Maps</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Show placeholder if no address is available
                    st.image("https://via.placeholder.com/400x200?text=No+Address+Available", use_column_width=True)
                
                # Send inquiry button
                email_to_use = "abhikatoldtrafford@gmail.com"  # Use this email for testing
                inquiry_disabled = not user_email or not user_name or email_status  # removed email validation since we're using test email
                
                if st.button(f"Send Inquiry", key=f"send_{name}_{idx}", disabled=inquiry_disabled, type="primary"):
                    # Add user info to event details
                    contact_details = event_details.copy()
                    contact_details["user_email"] = user_email
                    contact_details["user_name"] = user_name
                    contact_details["user_phone"] = user_phone
                    contact_details["user_company"] = user_company
                    contact_details["venue_name"] = name  # Add venue name for email subject
                    
                    with st.spinner(f"Sending inquiry to {name}..."):
                        progress_bar = st.progress(0)
                        for i in range(100):
                            time.sleep(0.01)
                            progress_bar.progress(i + 1)
                        
                        try:
                            # Use email.py to send inquiry
                            result = send_venue_request(
                                "credentials.json",  # Path to Gmail API credentials
                                email_to_use,  # Using test email
                                contact_details,
                                st.secrets.get("OPENAI_API_KEY", None)  # Optional OpenAI key
                            )
                            
                            if result.get("status") == "sent":
                                st.success(f"Inquiry sent successfully to {name}!")
                                st.session_state.emails_sent[name] = True
                            else:
                                st.error(f"Failed to send inquiry: {result.get('message')}")
                        except Exception as e:
                            st.error(f"Error sending inquiry: {str(e)}")
            
            st.markdown(f"""</div>""", unsafe_allow_html=True)
    
    # Add option to send to all
    st.markdown("### Bulk Action")
    
    all_have_emails = True  # Since we're using a test email for all venues
    
    contact_ready = user_name and user_email and all_have_emails
    all_sent = all(st.session_state.emails_sent.get(venue.get('name'), False) for venue in selected_venues)
    
    if st.button("Send Inquiries to All Selected Venues", disabled=not contact_ready or all_sent, type="primary"):
        # Add user info to event details
        contact_details = event_details.copy()
        contact_details["user_email"] = user_email
        contact_details["user_name"] = user_name
        contact_details["user_phone"] = user_phone
        contact_details["user_company"] = user_company
        
        # Get list of venues that haven't been sent emails yet
        venues_to_email = [v for v in selected_venues if not st.session_state.emails_sent.get(v.get('name'), False)]
        
        # Show spinner while sending emails
        with st.spinner(f"Sending inquiries to {len(venues_to_email)} venues..."):
            # Use improved email sender with progress tracking
            success_count = send_all_emails(venues_to_email, contact_details)
            
            if success_count > 0:
                st.success(f"Successfully sent {success_count} inquiries!")
    
    # Next steps section
    st.markdown("### What Happens Next")
    st.info("""
    📩 A copy of your inquiries will be sent to your email.
    ⏱️ Venues typically respond within 24-48 hours.
    📅 Once you receive responses, you can select the best venue for your event.
    """)

def main():
    # Determine which page to display
    if st.session_state.page == 'search':
        search_page()
    elif st.session_state.page == 'shortlist':
        shortlist_page()
    else:
        # Default to search page
        search_page()

if __name__ == "__main__":
    main()