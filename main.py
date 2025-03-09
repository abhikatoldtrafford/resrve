import streamlit as st
import json
from datetime import datetime

# Import backend functions
from app import find_best_restaurants, get_venue_recommendation

# Page configuration
st.set_page_config(
    page_title="Venue Finder", 
    page_icon="🍽️", 
    layout="wide"
)

# # Custom CSS for a modern, clean look
# st.markdown("""
# <style>
#     .stApp {
#         background-color: #f4f6f9;
#     }
#     .venue-card {
#         background-color: white;
#         border-radius: 12px;
#         padding: 20px;
#         margin-bottom: 20px;
#         box-shadow: 0 4px 10px rgba(0,0,0,0.05);
#         transition: all 0.3s ease;
#     }
#     .venue-card:hover {
#         transform: translateY(-5px);
#         box-shadow: 0 6px 15px rgba(0,0,0,0.1);
#     }
#     .score-badge {
#         background-color: #3b82f6;
#         color: white;
#         padding: 5px 10px;
#         border-radius: 20px;
#         font-weight: bold;
#     }
# </style>
# """, unsafe_allow_html=True)

def main():
    st.title("🍽️ Venue Finder")
    st.subheader("Discover the Perfect Venue for Your Corporate Event")

    # Event Details Form
    with st.form("event_details", clear_on_submit=False):
        # Basic Event Information
        st.markdown("### Event Basics")
        event_name = st.text_input("Event Name *", value="Engineering Team Offsite 2024")
        one_day_event = st.toggle("One Day Event")
        
        col1, col2 = st.columns(2)
        with col1:
            venue_type = st.selectbox("Venue Type *", 
                ["Select a venue type", "Conference Center", "Hotel", "Unique Venue"])
            start_date = st.date_input("Start Date *")
            event_time = st.time_input("Event Time *")
        
        with col2:
            event_type = st.selectbox("Event Type *", 
                ["Select an event type", "Conference", "Meeting", "Team Building"])
            end_date = st.date_input("End Date *")
        
        # Location and Proximity
        st.markdown("### Location Details")
        locations = st.multiselect(
            "Event Location(s) (limit 3 cities) *", 
            ["San Francisco", "New York", "Chicago", "Boston", "Seattle"],
            max_selections=3
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
            ["Private Only", "Semi-Private Only", "No Preference (See both)"]
        )
        
        # Event Specifics
        st.markdown("### Event Specifics")
        col3, col4, col5 = st.columns(3)
        with col3:
            venue_budget = st.number_input("Total Venue Budget ($) *", min_value=0, value=10000)
        with col4:
            attendees = st.number_input("Number of Attendees *", min_value=1, max_value=500, value=80)
        with col5:
            hotel_rooms = st.number_input("Hotel Rooms Needed", min_value=0, value=20)
        
        meeting_rooms = st.text_area(
            "Meeting Rooms & Layout", 
            value="80 pax classroom, 5 breakouts 20 pax",
            help="Describe your meeting space requirements"
        )
        
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
        
        origins = st.text_area(
            "Attendee Origins",
            value="Distributed across 22 countries, mostly from SF and NYC"
        )
        
        decision_date = st.date_input("Decision Date *")
        notes = st.text_area(
            "Additional Notes", 
            value="Date flexibility, open to sharing rooms"
        )
        
        search_started = st.radio(
            "Have you started searching?", 
            ["Yes", "No"], 
            horizontal=True
        )
        
        # Submit Button
        submitted = st.form_submit_button("Find Venues", type="primary")

    # Process Form Submission
    if submitted:
        # Prepare comprehensive event details dictionary
        event_details = {
            "event_name": event_name,
            "one_day_event": one_day_event,
            "venue_type": venue_type,
            "start_date": start_date.strftime("%m/%d/%Y"),
            "event_type": event_type,
            "end_date": end_date.strftime("%m/%d/%Y"),
            "event_time": event_time.strftime("%H:%M"),
            "locations": locations,
            "venue_budget": venue_budget,
            "attendees": attendees,
            "hotel_rooms": hotel_rooms,
            "meeting_rooms": meeting_rooms,
            "food_beverage": fb_details if fb_needed else "Not needed",
            "dietary_restrictions": dietary_restrictions,
            "special_requirements": special_requirements,
            "attendee_origins": origins,
            "decision_date": decision_date.strftime("%m/%d/%Y"),
            "notes": notes,
            "search_started": search_started,
            "private_preference": private_preference,
            "address_proximity": address_proximity,
            "neighborhood_preference": neighborhood_preference,
            "atmosphere": atmosphere
        }

        # Find Venues (Stage 1)
        with st.spinner("Finding perfect venues..."):
            stage1_results = find_best_restaurants(event_details)

        # Display Results
        if stage1_results and "top_restaurants" in stage1_results:
            venues = stage1_results["top_restaurants"]
            
            st.markdown("## Top Venue Recommendations")
            
            # Create columns for venues
            for idx, venue in enumerate(venues, 1):
                with st.container():
                    # Handle potential missing data
                    name = venue.get('name', 'Unnamed Venue')
                    address = venue.get('address', 'Address not available')
                    cuisine = venue.get('cuisine', 'Various Cuisine')
                    pricing = venue.get('pricing', 'Not specified')
                    
                    # Normalize score
                    score = venue.get('score', 0)
                    display_score = round(score * 10, 1) if score <= 1 else round(score, 1)
                    
                    st.markdown(f"""
                    <div class="venue-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3>{name}</h3>
                            <span class="score-badge">{display_score}/10 Match</span>
                        </div>
                        <p>
                        📍 {address} | 
                        🍽️ {cuisine} | 
                        💰 {pricing}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Expandable section for detailed recommendation
                    with st.expander(f"Detailed Recommendation for {name}"):
                        with st.spinner("Generating personalized recommendation..."):
                            recommendation = get_venue_recommendation(venue, event_details, idx)
                            st.write(recommendation)
            
            # Optional reasoning display
            if "selection_reasoning" in stage1_results:
                with st.expander("Why these venues?"):
                    st.write(stage1_results["selection_reasoning"])
        
        else:
            st.error("No venues found. Please adjust your search criteria.")

    # Sidebar with help and information
    with st.sidebar:
        st.header("🤔 How It Works")
        st.markdown("""
        ### Two-Stage AI Venue Finder
        1. **Stage 1**: AI analyzes your event needs
        2. **Stage 2**: Detailed venue recommendations
        
        ### Tips
        - Be specific about your requirements
        - Consider budget, atmosphere, and dietary needs
        - Explore different venue details
        """)

        st.divider()
        st.header("📞 Need Help?")
        st.markdown("""
        Contact our event specialists:
        - 📧 support@venuefinder.com
        - 📱 (555) 123-4567
        """)

if __name__ == "__main__":
    main()