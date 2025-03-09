import os
import json
import pandas as pd
import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import re
import streamlit as st

# Initialize the OpenAI client
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)


def strip_html_tags(text):
    """Remove HTML tags from a given string."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


# Function to generate embeddings for text
def generate_embedding(text):
    """Generate vector embeddings for a text string using OpenAI's embedding model."""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


# Function to load CSV data and handle embeddings
def load_csv_data(csv_path):
    """Load restaurant data from CSV and prepare embeddings."""
    try:
        # Define the path for CSV with embeddings
        embedding_csv_path = csv_path.replace('.csv', '_with_embeddings.csv')
        
        # Check if the CSV with embeddings already exists
        if os.path.exists(embedding_csv_path):
            print(f"Loading data with embeddings from {embedding_csv_path}...")
            df = pd.read_csv(embedding_csv_path, encoding='utf-8')
            
            # Convert embedding strings back to lists
            if 'embedding' in df.columns:
                df['embedding'] = df['embedding'].apply(
                    lambda x: json.loads(x) if isinstance(x, str) and x.startswith('[') else x
                )
            
            print(f"Loaded {len(df)} venues with existing embeddings")
        else:
            # Load the original CSV if no embeddings file exists
            print(f"Loading original data from {csv_path}...")
            df = pd.read_csv(csv_path, encoding='utf-8')
            print(f"Loaded {len(df)} venues")
            
            # Ensure we have the right column names
            if 'rag_data' in df.columns and 'ragdata' not in df.columns:
                df['ragdata'] = df['rag_data']
                
            # Add embedding column if it doesn't exist
            if 'embedding' not in df.columns:
                df['embedding'] = None
            
            # Track if we made any changes
            changes_made = False
            
            # Process each row that needs an embedding
            print("Checking for rows that need embeddings...")
            for idx, row in df.iterrows():
                # Only generate embedding if it's missing
                if pd.isna(row['embedding']):
                    if idx % 20 == 0:
                        print(f"Generating embedding for row {idx}/{len(df)}")
                    
                    # Get the text to embed from ragdata
                    if 'ragdata' not in row or pd.isna(row['ragdata']):
                        text_to_embed = "No venue information available"
                    else:
                        text_to_embed = row['ragdata']
                    
                    # Generate embedding
                    embedding = generate_embedding(text_to_embed)
                    df.at[idx, 'embedding'] = embedding
                    changes_made = True
            
            # Save the updated CSV if we made changes
            if changes_made:
                print(f"Saving updated CSV with embeddings to {embedding_csv_path}")
                
                # Make a copy for saving to avoid modifying our working dataframe
                df_to_save = df.copy()
                
                # Convert embeddings to JSON strings for CSV storage
                df_to_save['embedding'] = df_to_save['embedding'].apply(
                    lambda x: json.dumps(x) if x is not None else None
                )
                
                # Save to CSV
                df_to_save.to_csv(embedding_csv_path, index=False)
                print(f"Saved {len(df_to_save)} venues with embeddings")
            else:
                print("No new embeddings needed to be generated")
        
        return df
    
    except Exception as e:
        print(f"Error loading data: {e}")
        return None


# Updated Function to create search queries based on event details
def create_search_queries(event_details):
    """
    Create specialized search queries for different criteria.
    """
    # Pull out user inputs for convenience
    address_proximity = event_details.get('address_proximity', '')
    neighborhood_pref = event_details.get('neighborhood_preference', '')
    atmosphere = event_details.get('atmosphere', '')
    dietary_list = event_details.get('dietary_restrictions', [])
    private_preference = event_details.get('private_preference', 'No Preference')
    special_requirements = event_details.get('special_requirements', '')
    event_time = event_details.get('event_time', '')
    one_day_event = event_details.get('one_day_event', False)
    
    # Convert dietary restrictions to a comma-separated string
    dietary_text = ', '.join(dietary_list) if isinstance(dietary_list, list) else str(dietary_list)
    
    # Format event duration for clarity
    event_duration = "One Day Event" if one_day_event else f"Multi-day Event ({event_details.get('start_date', '')} to {event_details.get('end_date', '')})"
    
    # Build the distance portion of the overall query
    distance_query = ""
    if address_proximity:
        distance_query += f"Must be within ~5 miles of {address_proximity}. "
    if neighborhood_pref:
        distance_query += f"Strong preference for the {neighborhood_pref} area. "
    if not distance_query:
        distance_query = "No strict distance constraint specified. "

    queries = {
        "overall": f"""
            COMPREHENSIVE VENUE REQUIREMENTS:
            - Event Name: {event_details.get('event_name', 'Corporate Event')}
            - Event Type: {event_details.get('event_type', 'Meeting')}
            - Venue Category: {event_details.get('venue_type', 'Any')}
            - Date Range: {event_details.get('start_date', '')} to {event_details.get('end_date', '')}
            - One Day Event?: {one_day_event}
            - Locations: {', '.join(event_details.get('locations', ['New York']))}
            - Distance Query: {distance_query.strip()}
            - Desired Atmosphere: {atmosphere if atmosphere else 'No specific vibe stated'}
            - Private vs Semi-Private Preference: {private_preference}
            - Exact Attendee Count: {event_details.get('attendees', 30)}
            - Venue Budget: ${event_details.get('venue_budget', 10000)}
            - Meeting Room Configuration: {event_details.get('meeting_rooms', 'Conference style')}
            - Food & Beverage Needs: {event_details.get('food_beverage', 'Basic Catering')}
            - Dietary Restrictions: {dietary_text if dietary_text else 'N/A'}
            - Hotel Rooms Needed: {event_details.get('hotel_rooms', 0)}
            - Other Special Requirements: {special_requirements if special_requirements else 'None'}
            - Attendee Origins: {event_details.get('attendee_origins', 'Mixed/Unknown')}
            - Additional Notes: {event_details.get('notes', 'N/A')}
            - Decision Date: {event_details.get('decision_date', 'N/A')}
            - Event Time: {event_time}
            
            >>> PRIMARY GOAL: Return only those venues that (1) meet capacity and (2) fall within ~5 miles
            of the specified address or neighborhood (if given), while also respecting the budget,
            atmosphere/vibe, and other key factors above.
        """,
        
        "meeting_rooms": f"""
            PRIORITY: Meeting Space & Layout
            - MUST accommodate EXACTLY {event_details.get('attendees', 30)} attendees.
            - Required Room Configuration: {event_details.get('meeting_rooms', 'Multiple breakouts')}
            - Private/Semi-Private Preference: {private_preference}
            - Typical A/V Needs (projectors, microphones, etc.)
            - Emphasize convenience of location: {distance_query.strip()}
            - This is the PRIMARY focus of our venue search.
        """,
        
        "food": f"""
            PRIORITY: Food & Beverage
            - Must be suitable for a {event_details.get('event_type', 'business')} event
            - Specific F&B Requirements: {event_details.get('food_beverage', 'Basic Catering')}
            - Dietary Restrictions: {dietary_text if dietary_text else 'N/A'}
            - Must comfortably serve {event_details.get('attendees', 30)} people
            - Emphasize quality, variety, and any special dietary needs
            - Budget limit is ${event_details.get('venue_budget', 10000)}
            - Prefer location: {distance_query.strip()}
        """,
        
        "location": f"""
            PRIORITY: Location & Accessibility
            - Primary locations: {', '.join(event_details.get('locations', ['New York']))}
            - {distance_query.strip()}
            - Easy transportation access for {event_details.get('attendees', 30)} attendees
            - {f'Private/Semi-Private Space: {private_preference}' if private_preference != 'No Preference' else ''}
            - Suitable for {event_details.get('event_type', 'business')} events
            - Close to hotels/accommodations if needed: {event_details.get('hotel_rooms', 0)} rooms
            - This is a CRITICAL factor in our venue selection.
        """,
        
        "atmosphere": f"""
            PRIORITY: Ambiance & Atmosphere
            - SPECIFIC ATMOSPHERE DESIRED: {atmosphere if atmosphere else 'Professional yet comfortable'}
            - Must match the tone of a {event_details.get('event_type', 'business')} event
            - Suitable for {event_details.get('attendees', 30)} attendees
            - Setting should facilitate {event_details.get('event_type', 'business')} activities
            - {f'Private/Semi-Private Space: {private_preference}' if private_preference != 'No Preference' else ''}
            - Lighting, acoustics, and overall vibe are important considerations
        """,
        
        "budget": f"""
            PRIORITY: Budget & Cost
            - Hard budget ceiling of ${event_details.get('venue_budget', 10000)}
            - Venue + F&B must fit within this budget for {event_details.get('attendees', 30)} attendees
            - Seek all-inclusive or transparent pricing (avoid hidden fees)
            - Keep location preference in mind: {distance_query.strip()}
            - Budget needs to cover:
              - Venue rental for {event_duration}
              - Food & beverage: {event_details.get('food_beverage', 'Basic Catering')}
              - Meeting space: {event_details.get('meeting_rooms', 'Conference style')}
              - Any technical requirements: {special_requirements if special_requirements else 'Standard A/V'}
        """
    }

    return queries


# Function to find top matches for each criterion
def find_top_matches(df, event_details, use_specialized_criteria=True):
    """Find top restaurant matches based on embedding similarity."""
    try:
        if use_specialized_criteria:
            print("Finding top matches using specialized criteria...")
            queries = create_search_queries(event_details)
            
            # Initialize dictionary to store results
            top_matches = {}
            
            # Track venues we've already selected to maintain diversity
            all_selected_venues = set()
            
            # Process each criterion
            for criterion, query in queries.items():
                print(f"Processing criterion: {criterion}")
                
                # Generate embedding for the query
                query_embedding = generate_embedding(query)
                
                # Calculate similarity with all restaurants
                similarities = []
                for idx, row in df.iterrows():
                    if row['embedding'] is not None:
                        similarity = cosine_similarity([query_embedding], [row['embedding']])[0][0]
                        similarities.append((idx, similarity, row))
                
                # Sort by similarity score
                similarities.sort(key=lambda x: x[1], reverse=True)
                
                # Get top matches for this criterion (more for overall, fewer for specialized criteria)
                num_matches = 25 if criterion == "overall" else 5
                
                # Add diversity to selection - don't pick same venue for multiple criteria if possible
                seen_venues = set()
                diverse_matches = []
                
                # First add restaurants not selected in any previous criteria (for overall diversity)
                for idx, score, row in similarities:
                    venue_name = row.get('Restaurant name', row.get('name', f'Restaurant {idx}'))
                    
                    # Only add venues we haven't seen in this criterion and preferably in any criterion
                    if venue_name not in seen_venues and len(diverse_matches) < num_matches:
                        # Prioritize venues we haven't selected for any criterion yet
                        if criterion != "overall" and venue_name in all_selected_venues:
                            # If already selected elsewhere and not overall, only add if we're short on options
                            if len([v for v in similarities if v[2].get('Restaurant name', v[2].get('name', f'Restaurant {v[0]}')) not in all_selected_venues]) < num_matches:
                                diverse_matches.append((idx, score, row))
                                seen_venues.add(venue_name)
                        else:
                            diverse_matches.append((idx, score, row))
                            seen_venues.add(venue_name)
                            all_selected_venues.add(venue_name)
                
                # Fill remaining slots with top-scoring venues if needed
                if len(diverse_matches) < num_matches:
                    for idx, score, row in similarities:
                        venue_name = row.get('Restaurant name', row.get('name', f'Restaurant {idx}'))
                        if venue_name not in seen_venues and len(diverse_matches) < num_matches:
                            diverse_matches.append((idx, score, row))
                            seen_venues.add(venue_name)
                            all_selected_venues.add(venue_name)
                
                # Extract restaurant details for top matches
                top_matches[criterion] = [{
                    'id': int(idx),
                    'name': row.get('Restaurant name', row.get('name', f'Restaurant {idx}')),
                    'score': round(float(score), 4),
                    'address': row.get('Physical Address', row.get('address', '')),
                    'neighborhood': row.get('Neighborhood', row.get('neighborhood', '')),
                    'cuisine': row.get('Cuisine', row.get('cuisine', '')),
                    'pricing': row.get('General Pricing', row.get('pricing', '')),
                    'ragdata': row.get('ragdata', row.get('rag_data', ''))
                } for idx, score, row in diverse_matches]
                
                print(f"Found {len(top_matches[criterion])} top matches for {criterion}")
            
            return top_matches
        
        else:
            print("Finding top matches using overall criterion only...")
            
            # Create a comprehensive query
            overall_query = create_search_queries(event_details)["overall"]
            
            # Generate embedding for the query
            query_embedding = generate_embedding(overall_query)
            
            # Calculate similarity with all restaurants
            similarities = []
            for idx, row in df.iterrows():
                if row['embedding'] is not None:
                    similarity = cosine_similarity([query_embedding], [row['embedding']])[0][0]
                    similarities.append((idx, similarity, row))
            
            # Sort by similarity score
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Get top 25 matches
            top_matches = [{
                'id': int(idx),
                'name': row.get('Restaurant name', row.get('name', f'Restaurant {idx}')),
                'score': round(float(score), 4),
                'address': row.get('Physical Address', row.get('address', '')),
                'neighborhood': row.get('Neighborhood', row.get('neighborhood', '')),
                'cuisine': row.get('Cuisine', row.get('cuisine', '')),
                'pricing': row.get('General Pricing', row.get('pricing', '')),
                'ragdata': row.get('ragdata', row.get('rag_data', ''))
            } for idx, score, row in similarities[:25]]
            
            return {"overall": top_matches}
    
    except Exception as e:
        print(f"Error finding top matches: {e}")
        return None


# STAGE 1: GPT-driven selection of top 15 restaurants
def get_top_restaurants(top_matches, event_details):
    """
    STAGE 1: Use GPT to select the top 15 restaurants from all matches.
    Takes into account event details and venue characteristics.
    """
    try:
        print("STAGE 1: Getting top 15 restaurants with GPT...")
        
        # Step 1: Prepare a flat list of all venues
        all_venues = []
        for criterion, venues in top_matches.items():
            all_venues.extend(venues)
        
        # Create a lookup dictionary for venues by name
        venue_dict = {}
        for venue in all_venues:
            venue_name = venue['name']
            # If venue appears multiple times, keep the highest-scoring instance
            if venue_name not in venue_dict or venue['score'] > venue_dict[venue_name]['score']:
                venue_dict[venue_name] = venue
        
        # Format event details for the prompt
        event_summary = f"""
        Event: {event_details.get('event_name', 'Corporate Event')}
        Type: {event_details.get('event_type', 'Meeting')}
        Attendees: {event_details.get('attendees', 30)}
        Budget: ${event_details.get('venue_budget', 10000)}
        Meeting Configuration: {event_details.get('meeting_rooms', 'Conference style')}
        Food & Beverage: {event_details.get('food_beverage', 'Basic Catering')}
        Locations: {', '.join(event_details.get('locations', ['New York']))}
        """
        
        # Extract priority requirements
        priority_requirements = {
            "locations": event_details.get('locations', ['New York']),
            "dietary_restrictions": event_details.get('dietary_restrictions', []),
            "address_proximity": event_details.get('address_proximity', ''),
            "neighborhood_preference": event_details.get('neighborhood_preference', ''),
            "atmosphere": event_details.get('atmosphere', ''),
            "private_preference": event_details.get('private_preference', 'No Preference'),
            "attendees": event_details.get('attendees', 30),
            "budget": event_details.get('venue_budget', 10000)
        }
        
        # First stage: Get shortlist of restaurant names using enforced JSON response
        try:
            print("Stage 1: Getting shortlist of restaurants...")
            shortlist_prompt = f"""
            Select the 15 best restaurant venues for this event from the list provided.
            
            EVENT DETAILS:
            {event_summary}
            
            PRIORITY REQUIREMENTS (MOST IMPORTANT):
            - Locations: {', '.join(priority_requirements['locations'])}
            - Dietary Restrictions: {', '.join(priority_requirements['dietary_restrictions']) if priority_requirements['dietary_restrictions'] else 'None'}
            - Address Proximity: {priority_requirements['address_proximity'] if priority_requirements['address_proximity'] else 'Not specified'}
            - Neighborhood: {priority_requirements['neighborhood_preference'] if priority_requirements['neighborhood_preference'] else 'Not specified'}
            - Atmosphere: {priority_requirements['atmosphere'] if priority_requirements['atmosphere'] else 'Not specified'}
            - Private/Semi-Private: {priority_requirements['private_preference']}
            - Must accommodate: {priority_requirements['attendees']} attendees
            - Budget limit: ${priority_requirements['budget']}
            
            AVAILABLE VENUES:
            {json.dumps(venue_dict, indent=2)}
            
            Task: Choose the 15 best restaurant venues that:
            1. Best meet the PRIORITY REQUIREMENTS above
            2. Have suitable capacity for the attendee count
            3. Fall within budget constraints
            4. Are most convenient for the given location preferences
            
            Return a JSON object with two fields:
            1. "selected_restaurants": List of the 15 best venue names
            2. "reasoning": Brief explanation of your selection criteria
            """
            
            shortlist_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a venue selection specialist."},
                    {"role": "user", "content": shortlist_prompt}
                ],
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            # Parse the response to get restaurant names
            shortlist_json = json.loads(shortlist_response.choices[0].message.content)
            restaurant_names = shortlist_json.get("selected_restaurants", [])
            selection_reasoning = shortlist_json.get("reasoning", "")
            
            print(f"Shortlist created with {len(restaurant_names)} restaurants")
            
        except Exception as e:
            print(f"Error in Stage 1: {e}")
            # Fallback: use top scored venues
            print("Using fallback: top scored venues by score")
            sorted_venues = sorted(all_venues, key=lambda v: v.get('score', 0), reverse=True)
            seen = set()
            restaurant_names = []
            for venue in sorted_venues:
                if venue['name'] not in seen and len(restaurant_names) < 15:
                    restaurant_names.append(venue['name'])
                    seen.add(venue['name'])
            selection_reasoning = "Selected based on similarity scores (algorithmic fallback)."
        
        # Prepare the top 15 results
        top_15_venues = []
        for restaurant_name in restaurant_names[:15]:
            # Find the venue data - use exact match first
            venue_data = venue_dict.get(restaurant_name)
            
            # If no exact match, look for partial matches
            if not venue_data:
                for name, venue in venue_dict.items():
                    if restaurant_name.lower() in name.lower() or name.lower() in restaurant_name.lower():
                        venue_data = venue
                        break
            
            # Add to result if found
            if venue_data:
                top_15_venues.append(venue_data)
        
        # If we couldn't find 15 venues, fill with top-scoring ones
        if len(top_15_venues) < 15:
            sorted_venues = sorted(all_venues, key=lambda v: v.get('score', 0), reverse=True)
            seen_names = {venue['name'] for venue in top_15_venues}
            
            for venue in sorted_venues:
                if venue['name'] not in seen_names and len(top_15_venues) < 15:
                    top_15_venues.append(venue)
                    seen_names.add(venue['name'])
        
        # Prepare final result
        result = {
            "top_restaurants": top_15_venues,
            "selection_reasoning": selection_reasoning,
            "event_summary": {
                "event_name": event_details.get('event_name', 'Corporate Event'),
                "event_type": event_details.get('event_type', 'Meeting'),
                "attendees": event_details.get('attendees', 30),
                "budget": event_details.get('venue_budget', 10000),
                "meeting_config": event_details.get('meeting_rooms', 'Conference style'),
                "food_beverage": event_details.get('food_beverage', 'Basic Catering'),
                "locations": event_details.get('locations', ['New York'])
            }
        }
        
        print(f"STAGE 1 complete: Selected top {len(top_15_venues)} restaurants")
        return result
        
    except Exception as e:
        print(f"Error in Stage 1: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "top_restaurants": []}


# STAGE 2: Generate detailed recommendation for a single venue
def generate_venue_recommendation(venue_data, event_details, venue_index=1):
    """
    STAGE 2: Generate a detailed recommendation for a single venue.
    This will be called individually for each venue tab as needed.
    """
    try:
        print(f"STAGE 2: Generating detailed recommendation for {venue_data['name']}...")
        
        # Format event details for the prompt
        event_summary = f"""
        Event: {event_details.get('event_name', 'Corporate Event')}
        Type: {event_details.get('event_type', 'Meeting')}
        Attendees: {event_details.get('attendees', 30)}
        Budget: ${event_details.get('venue_budget', 10000)}
        Meeting Configuration: {event_details.get('meeting_rooms', 'Conference style')}
        Food & Beverage: {event_details.get('food_beverage', 'Basic Catering')}
        Locations: {', '.join(event_details.get('locations', ['New York']))}
        """
        
        # Generate detailed recommendation for this restaurant
        detail_prompt = f"""
        Create a detailed recommendation for the restaurant "{venue_data['name']}" for this event:
        
        EVENT DETAILS:
        {event_details}
        
        VENUE INFORMATION:
        {json.dumps(venue_data, indent=2)}
        
        Format your recommendation exactly like this:
        
        ### {venue_index}. {venue_data['name']}
        [Brief introduction to the restaurant]
        
        **Why it's perfect for your event:**
        - [Specific reason with reference to event requirements (1 line)]
        - [Specific reason with reference to event requirements (1 line)]

        
        **Meeting Space:** [How it meets meeting room requirements (1-2 lines)]
        
        **Food & Beverage:** [How it meets food/beverage requirements (1-2 lines)]
        
        **Considerations:** [Any limitations or things to be aware of (1-2 lines)]
        
        **Confidence Score:** [X/10] - [Brief explanation in plain text (6-10)]
        """
        
        detail_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a restaurant recommendation specialist."},
                {"role": "user", "content": detail_prompt}
            ],
            temperature=0.7
        )
        
        recommendation = detail_response.choices[0].message.content
        
        # Return the formatted recommendation as a string
        return recommendation.strip()
        
    except Exception as e:
        print(f"Error generating recommendation for {venue_data['name']}: {e}")
        import traceback
        traceback.print_exc()
        
        # Return error message in the correct format
        return f"""
        ### {venue_index}. {venue_data['name']}
        
        *Error: Could not generate detailed recommendation for this venue.*
        
        **Error Details:** {str(e)}
        """


# New structured approach for recommendation system
def find_best_restaurants(event_details_json, csv_path="cleaned_restaurants.csv", use_specialized_criteria=True):
    """
    Main entry point for the recommendation system using the two-stage approach.
    
    Stage 1: Return top 15 restaurants selected by GPT.
    Stage 2: Generate detailed recommendations for each restaurant on demand.
    """
    try:
        start_time = datetime.now()
        print(f"Starting restaurant recommendation process at {start_time}")
        
        # Parse the event details
        if isinstance(event_details_json, str):
            event_details = json.loads(event_details_json)
        else:
            event_details = event_details_json
        
        # Load the restaurant data
        df = load_csv_data(csv_path)
        if df is None:
            return {"error": "Failed to load restaurant data."}
        
        # Find top matches
        top_matches = find_top_matches(df, event_details, use_specialized_criteria)
        if top_matches is None:
            return {"error": "Failed to find top matches."}
        
        # STAGE 1: Get top 15 restaurants using GPT
        stage1_result = get_top_restaurants(top_matches, event_details)
        
        # Calculate processing time for Stage 1
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        print(f"Stage 1 completed in {processing_time:.2f} seconds")
        
        # Add timing information
        stage1_result["processing_time"] = processing_time
        
        # Return the Stage 1 result (Stage 2 will be called separately per venue as needed)
        return stage1_result
        
    except Exception as e:
        print(f"Error in find_best_restaurants: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "top_restaurants": []}


# Function to handle Stage 2 - get detailed recommendation for a single venue
def get_venue_recommendation(venue_data, event_details, venue_index=1):
    """Wrapper function to get a detailed recommendation for a single venue."""
    return generate_venue_recommendation(venue_data, event_details, venue_index)


if __name__ == "__main__":
    # Sample event details for testing
    sample_event = {
        "event_name": "Engineering Team Offsite 2024",
        "one_day_event": False,
        "venue_type": "Unique Venue",
        "start_date": "03/01/2025",
        "event_type": "Team Building",
        "end_date": "03/01/2025",
        "locations": ["New York"],
        "venue_budget": 10000,
        "attendees": 80,
        "hotel_rooms": 20,
        "meeting_rooms": "80 pax classroom, 5 breakouts 20 pax",
        "food_beverage": "indian cuisine preferred",
        "decision_date": "03/01/2025",
        "notes": "Date flexibility, open to sharing rooms"
    }
    
    # Test Stage 1
    stage1_results = find_best_restaurants(
        sample_event,
        csv_path="updated_cleaned_restaurants.csv", 
        use_specialized_criteria=True
    )
    
    print(f"Found {len(stage1_results['top_restaurants'])} venues in {stage1_results['processing_time']:.2f} seconds")
    print(f"Selection reasoning: {stage1_results['selection_reasoning']}")
    
    # Test Stage 2 for first venue
    if stage1_results["top_restaurants"]:
        first_venue = stage1_results["top_restaurants"][0]
        recommendation = get_venue_recommendation(first_venue, sample_event, 1)
        print("\nSample recommendation for first venue:")
        print(recommendation)