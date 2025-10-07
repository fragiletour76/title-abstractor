import streamlit as st
import json

def render_chatbot(abstract, db, gemini_client):
    """
    AI Chatbot that can answer questions about the document
    """
    st.subheader("💬 Ask Questions About This Abstract")
    st.caption("Ask anything about the property, parties, dates, or chain of title")
    
    # Load abstract data
    if abstract.is_edited and abstract.edited_json_data:
        data = json.loads(abstract.edited_json_data)
    else:
        data = json.loads(abstract.json_data)
    
    # Initialize chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about this abstract..."):
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = _get_ai_response(prompt, data, abstract, db, gemini_client)
                st.markdown(response)
        
        st.session_state.chat_history.append({"role": "assistant", "content": response})
    
    # Clear chat button
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()

def _get_ai_response(question, data, abstract, db, gemini_client):
    """
    Generate AI response based on abstract data
    """
    # Build context from abstract data
    context = f"""You are a helpful assistant analyzing a title abstract.

ABSTRACT DATA:
{json.dumps(data, indent=2)}

FILE: {abstract.filename}
PAGES: {abstract.pages_processed}
DOCUMENTS EXTRACTED: {len(data.get('documents', []))}

Answer the user's question based on this abstract data. Be specific and cite document numbers when relevant.
If the information isn't in the abstract, say so clearly.
"""
    
    prompt = f"{context}\n\nQUESTION: {question}\n\nANSWER:"
    
    try:
        # Use Gemini to generate response
        import google.generativeai as genai
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content(
            prompt,
            generation_config={'temperature': 0.7, 'max_output_tokens': 2000}
        )
        
        return response.text
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"
