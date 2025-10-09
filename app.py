import streamlit as st
import os
import json
import time
import re
import shutil
from io import StringIO
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from src.abstractor import TitleAbstractor
from src.renderer import render_markdown
from database import Database

load_dotenv()

st.set_page_config(page_title="Title Abstractor", page_icon="📄", layout="wide")

@st.cache_resource
def init_system():
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        st.error("Please set GOOGLE_API_KEY in .env file")
        st.stop()
    return TitleAbstractor(api_key), Database()

abstractor, db = init_system()

# Initialize session state
if 'current_abstract_id' not in st.session_state:
    st.session_state.current_abstract_id = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'view'
if 'working_json' not in st.session_state:
    st.session_state.working_json = None

# Header with actions
col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
with col1:
    st.title("📄 Title Abstractor")
with col2:
    if st.button("🆕 New Abstract", use_container_width=True):
        st.session_state.current_abstract_id = None
        st.session_state.view_mode = 'view'
        st.session_state.working_json = None
        st.rerun()
with col3:
    if st.button("📚 View History", use_container_width=True):
        st.session_state.current_abstract_id = None
        st.session_state.view_mode = 'history'
        st.rerun()
with col4:
    if st.button("⚙️ Settings", use_container_width=True):
        st.session_state.current_abstract_id = None
        st.session_state.view_mode = 'settings'
        st.rerun()

st.divider()

# Main content area
if st.session_state.view_mode == 'history':
    # HISTORY VIEW
    st.subheader("Abstract History")
    
    abstracts = db.get_all_abstracts()
    
    if not abstracts:
        st.info("No abstracts yet. Click 'New Abstract' to get started!")
    else:
        for abstract in abstracts:
            with st.expander(f"{abstract.filename} - {abstract.created_at.strftime('%Y-%m-%d %H:%M')}"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Pages", abstract.pages_processed)
                with col2:
                    st.metric("Cost", f"${abstract.cost_estimate:.2f}")
                with col3:
                    st.metric("Documents", abstract.json_data.count('"documentType"') if abstract.json_data else 0)
                with col4:
                    if abstract.is_edited:
                        st.metric("Status", "✏️ Edited")
                    else:
                        st.metric("Status", "Original")
                
                if st.button("Open This Abstract", key=f"open_{abstract.id}"):
                    st.session_state.current_abstract_id = abstract.id
                    st.session_state.view_mode = 'view'
                    st.rerun()

elif st.session_state.view_mode == 'settings':
    # SETTINGS VIEW
    st.subheader("⚙️ Settings")
    
    tab1, tab2, tab3 = st.tabs(["Prompts", "Configuration", "About"])
    
    with tab1:
        st.markdown("### Prompt Management")
        st.caption("Customize extraction prompts for different document types")
        
        from config.prompts import BASE_PROMPT, DOC_TYPE_PROMPTS, get_combined_prompt
        
        # Base prompt editor
        with st.expander("📝 Base Prompt (Core Instructions)", expanded=False):
            edited_base = st.text_area(
                "Edit base prompt:",
                value=BASE_PROMPT,
                height=400,
                key="base_prompt_editor"
            )
            
            if st.button("💾 Save Base Prompt"):
                # Save to file
                backup_path = "config/prompts_backup.py"
                if os.path.exists("config/prompts.py"):
                    shutil.copy2("config/prompts.py", backup_path)
                    st.success(f"✓ Backup saved to {backup_path}")
                
                with open("config/prompts.py", "r") as f:
                    content = f.read()
                
                # Replace BASE_PROMPT
                pattern = r'BASE_PROMPT = """.*?"""'
                new_content = re.sub(pattern, f'BASE_PROMPT = """{edited_base}"""', content, flags=re.DOTALL)
                
                with open("config/prompts.py", "w") as f:
                    f.write(new_content)
                
                st.success("✓ Base prompt updated! Restart the app to apply changes.")
                st.info("Run: `streamlit run app.py` to reload")
        
        st.divider()
        
        # Document-type specific prompts
        st.markdown("### Document-Type Specific Prompts")
        
        for doc_type, prompt_text in DOC_TYPE_PROMPTS.items():
            with st.expander(f"📄 {doc_type.upper()} Prompt", expanded=False):
                edited_prompt = st.text_area(
                    f"Edit {doc_type} prompt:",
                    value=prompt_text,
                    height=200,
                    key=f"{doc_type}_prompt_editor"
                )
                
                if st.button(f"💾 Save {doc_type.title()} Prompt", key=f"save_{doc_type}"):
                    # Save to file
                    backup_path = "config/prompts_backup.py"
                    if os.path.exists("config/prompts.py"):
                        shutil.copy2("config/prompts.py", backup_path)
                    
                    with open("config/prompts.py", "r") as f:
                        content = f.read()
                    
                    # Replace specific doc type prompt
                    pattern = f'"{doc_type}": """.*?"""'
                    replacement = f'"{doc_type}": """{edited_prompt}"""'
                    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
                    
                    with open("config/prompts.py", "w") as f:
                        f.write(new_content)
                    
                    st.success(f"✓ {doc_type.title()} prompt updated! Restart to apply.")
        
        st.divider()
        
        # Test prompt
        st.markdown("### 🧪 Test Combined Prompt")
        doc_types = st.multiselect(
            "Select document types to include:",
            options=list(DOC_TYPE_PROMPTS.keys()),
            default=["deed", "mortgage"]
        )
        
        if st.button("Generate Preview"):
            combined = get_combined_prompt(doc_types)
            st.code(combined, language="markdown")
            st.caption(f"Total length: {len(combined)} characters")
    
    with tab2:
        st.markdown("### Configuration")
        
        # API Settings
        st.markdown("#### API Configuration")
        current_key = os.getenv('GOOGLE_API_KEY', '')
        masked_key = current_key[:10] + "..." if current_key else "Not set"
        st.text_input("Google API Key", value=masked_key, disabled=True)
        st.caption("To change API key, edit `.env` file")
        
        st.divider()
        
        # Processing Settings
        st.markdown("#### Processing Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            hourly_rate = st.number_input(
                "Associate Hourly Rate ($)",
                min_value=10,
                max_value=100,
                value=23,
                step=1
            )
        with col2:
            wpm = st.number_input(
                "Typing Speed (WPM)",
                min_value=30,
                max_value=100,
                value=50,
                step=5
            )
        
        st.caption("These settings affect time/cost calculations")
        
        if st.button("💾 Save Processing Settings"):
            st.info("Note: Settings persistence will be implemented in a future update")
    
    with tab3:
        st.markdown("### About Title Abstractor")
        
        st.markdown("""
        **Version:** 1.0.0  
        **Built with:** Streamlit, Google Gemini 2.0, Python  
        
        **Features:**
        - AI-powered document extraction
        - Two-pass processing for accuracy
        - Interactive PDF viewer with zoom
        - Chain of title visualization
        - AI chatbot for Q&A
        - Time & cost savings tracking
        - Processing history & error logs
        
        **Processing Method:**
        - Pass 1: Document inventory
        - Pass 2: Detailed extraction per document
        - Pass 3: Chain of title analysis
        """)

elif st.session_state.current_abstract_id is None:
    # NEW ABSTRACT UPLOAD
    st.subheader("Upload New Abstract")
    
    uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
    
    if uploaded_file:
        st.info(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        if st.button("Process Document", type="primary", use_container_width=True):
            temp_path = f"temp_{uploaded_file.name}"
            
            with open(temp_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            # Initialize processing log
            processing_log = []
            
            def log_message(msg, level="INFO"):
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] [{level}] {msg}"
                processing_log.append(log_entry)
                return msg
            
            with st.status("Processing document...", expanded=True) as status:
                try:
                    # Convert PDF
                    st.write(log_message("📄 Converting PDF to images..."))
                    from src.pdf_processor import PDFProcessor
                    processor = PDFProcessor()
                    images = processor.pdf_to_images(temp_path)
                    st.write(log_message(f"✓ Converted {len(images)} pages"))
                    
                    # Upload
                    st.write(log_message("☁️ Uploading to Gemini Files API..."))
                    from src.file_uploader import FileUploader
                    uploader = FileUploader(os.getenv('GOOGLE_API_KEY'))
                    file_info = uploader.upload_pdf(temp_path, uploaded_file.name)
                    st.write(log_message(f"✓ Uploaded successfully (File ID: {file_info['name']})"))
                    
                    # Pass 1: Inventory
                    st.write(log_message("🔍 **PASS 1:** Creating document inventory..."))
                    inventory = abstractor._get_inventory(file_info, len(images))
                    st.write(log_message(f"✓ Found {len(inventory)} documents"))
                    
                    # Deduplicate inventory
                    from deduplication import deduplicate_inventory
                    inventory = deduplicate_inventory(inventory)
                    st.write(log_message(f"✓ After deduplication: {len(inventory)} unique documents:"))
                    
                    for i, doc_info in enumerate(inventory, 1):
                        pages = doc_info.get('pages', {})
                        msg = f"  {i}. {doc_info.get('type', 'Unknown')} (pages {pages.get('start', '?')}-{pages.get('end', '?')})"
                        st.write(log_message(msg))
                    
                    # Pass 2: Detailed extraction with timing
                    st.write("")
                    st.write(log_message("🔍 **PASS 2:** Extracting document details..."))
                    
                    start_time = time.time()
                    all_documents = []
                    
                    progress_bar = st.progress(0)
                    for i, doc_info in enumerate(inventory, 1):
                        doc_type = doc_info.get('type', 'Unknown')
                        pages = doc_info.get('pages', {})
                        
                        status_text = st.empty()
                        msg = f"  Processing {i}/{len(inventory)}: {doc_type} (pages {pages.get('start', '?')}-{pages.get('end', '?')})..."
                        status_text.write(log_message(msg))
                        
                        try:
                            doc_detail = abstractor._extract_document_detail(file_info, doc_info, i)
                            doc_detail['pageLocation'] = pages
                            all_documents.append(doc_detail)
                            msg = f"  ✓ {i}/{len(inventory)}: {doc_type} complete"
                            status_text.write(log_message(msg))
                        except Exception as e:
                            msg = f"  ✗ {i}/{len(inventory)}: {doc_type} failed - {str(e)}"
                            status_text.write(log_message(msg, "ERROR"))
                        
                        progress_bar.progress(i / len(inventory))
                    
                    st.write(log_message(f"✓ Extracted {len(all_documents)} documents"))
                    
                    # Pass 2.5: Deduplicate extracted documents
                    st.write("")
                    st.write(log_message("🔍 **DEDUPLICATION:** Removing duplicate documents..."))
                    from deduplication import deduplicate_documents
                    all_documents = deduplicate_documents(all_documents)
                    st.write(log_message(f"✓ After deduplication: {len(all_documents)} unique documents"))
                    
                    # Cleanup
                    uploader.delete_file(file_info['name'])
                    st.write(log_message("✓ Cleaned up temporary files"))
                    
                    # Pass 3: Chain analysis
                    st.write("")
                    st.write(log_message("🔗 **PASS 3:** Analyzing chain of title..."))
                    from src.chain_analyzer import ChainAnalyzer
                    analyzer = ChainAnalyzer()
                    sorted_docs, warnings = analyzer.analyze_chain(all_documents)
                    
                    if warnings:
                        st.write(log_message(f"⚠️ Found {len(warnings)} warnings:", "WARNING"))
                        for warning in warnings:
                            st.write(log_message(f"  - {warning}", "WARNING"))
                    else:
                        st.write(log_message("✓ No issues detected"))
                    
                    # Calculate time metrics
                    processing_time_seconds = time.time() - start_time
                    
                    num_documents = len(sorted_docs)
                    num_deeds = sum(1 for d in sorted_docs if 'deed' in d.get('documentType', '').lower())
                    num_mortgages = sum(1 for d in sorted_docs if 'mortgage' in d.get('documentType', '').lower())
                    total_chars = sum(len(d.get('property', {}).get('legalDescription', '')) for d in sorted_docs)
                    
                    manual_time_minutes = (
                        (num_documents * 4) +
                        (num_deeds * 1) +
                        (num_mortgages * 1) +
                        (total_chars / 250)
                    )
                    
                    time_saved_minutes = manual_time_minutes - (processing_time_seconds / 60)
                    time_saved_percent = (time_saved_minutes / manual_time_minutes * 100) if manual_time_minutes > 0 else 0
                    
                    hourly_rate = 23
                    manual_cost = (manual_time_minutes / 60) * hourly_rate
                    ai_cost = (processing_time_seconds / 60 / 60) * hourly_rate
                    cost_saved = manual_cost - ai_cost
                    
                    log_message(f"⏱️ Processing completed in {round(processing_time_seconds, 1)} seconds")
                    log_message(f"💰 Estimated savings: ${round(cost_saved, 2)}")
                    
                    # Build result
                    result = {
                        "source": {"fileName": uploaded_file.name, "county": "", "state": "NY"},
                        "review": {
                            "totalPagesProcessed": len(images),
                            "allPagesReviewed": True,
                            "chainWarnings": warnings,
                            "extractionMethod": "two-pass-hybrid",
                            "documentsExtracted": len(sorted_docs),
                            "timeMetrics": {
                                "aiProcessingSeconds": round(processing_time_seconds, 1),
                                "aiProcessingMinutes": round(processing_time_seconds / 60, 1),
                                "manualEstimateMinutes": round(manual_time_minutes, 1),
                                "timeSavedMinutes": round(time_saved_minutes, 1),
                                "timeSavedPercent": round(time_saved_percent, 1),
                                "hourlyRate": hourly_rate,
                                "manualCost": round(manual_cost, 2),
                                "aiCost": round(ai_cost, 2),
                                "costSaved": round(cost_saved, 2)
                            }
                        },
                        "documents": sorted_docs
                    }
                    
                    st.write("")
                    st.write(log_message("📝 Rendering markdown output..."))
                    markdown = render_markdown(result)
                    st.write(log_message("✓ Markdown generated"))
                    
                    st.write(log_message("💾 Saving to database..."))
                    
                    # Convert log to string
                    log_text = "\n".join(processing_log)
                    
                    abstract_id = db.save_abstract(
                        filename=uploaded_file.name,
                        json_data=result,
                        markdown=markdown,
                        pages=result['review']['totalPagesProcessed'],
                        cost=abstractor.gemini.estimate_cost(result['review']['totalPagesProcessed']),
                        pdf_path=temp_path,
                        processing_log=log_text
                    )
                    st.write(log_message(f"✓ Saved with ID: {abstract_id}"))
                    
                    # Display time savings summary
                    time_metrics = result.get('review', {}).get('timeMetrics', {})
                    if time_metrics:
                        st.write("")
                        st.write("⏱️  **Time & Cost Savings:**")
                        st.write(f"  • AI Processing: {time_metrics.get('aiProcessingMinutes', 0)} minutes")
                        st.write(f"  • Manual Estimate: {time_metrics.get('manualEstimateMinutes', 0)} minutes")
                        st.write(f"  • Time Saved: {time_metrics.get('timeSavedMinutes', 0)} minutes ({time_metrics.get('timeSavedPercent', 0)}%)")
                        st.write(f"  • Cost Saved: ${time_metrics.get('costSaved', 0)} (at ${time_metrics.get('hourlyRate', 23)}/hour)")
                    
                    status.update(label="✅ Processing complete!", state="complete")
                    
                    st.session_state.current_abstract_id = abstract_id
                    st.session_state.view_mode = 'view'
                    
                    st.balloons()
                    st.rerun()
                    
                except Exception as e:
                    error_msg = f"❌ FATAL ERROR: {str(e)}"
                    log_message(error_msg, "ERROR")
                    status.update(label="❌ Processing failed", state="error")
                    st.error(f"Error: {str(e)}")
                    import traceback
                    tb = traceback.format_exc()
                    log_message(tb, "ERROR")
                    st.code(tb)
                    
                    # Save partial log even on failure
                    log_text = "\n".join(processing_log)
                    with open(f"error_log_{uploaded_file.name}.txt", "w") as f:
                        f.write(log_text)
                    st.warning(f"Error log saved to: error_log_{uploaded_file.name}.txt")
                    
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

else:
    # ABSTRACT VIEWER/EDITOR
    abstract = db.get_abstract(st.session_state.current_abstract_id)
    
    if not abstract:
        st.error("Abstract not found")
        st.session_state.current_abstract_id = None
        st.rerun()
    
    # Abstract header
    st.subheader(f"📄 {abstract.filename}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pages", abstract.pages_processed)
    with col2:
        st.metric("Documents", abstract.json_data.count('"documentType"') if abstract.json_data else 0)
    with col3:
        st.metric("Created", abstract.created_at.strftime('%Y-%m-%d'))
    with col4:
        if abstract.is_edited:
            st.caption(f"Edited {abstract.last_edited_at.strftime('%Y-%m-%d')}")
        else:
            st.caption("Original")
    
    # Time savings metrics
    if abstract.json_data:
        try:
            data = json.loads(abstract.json_data)
            time_metrics = data.get('review', {}).get('timeMetrics', {})
            
            if time_metrics:
                st.divider()
                st.subheader("⏱️ Time & Cost Savings")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("AI Processing", f"{time_metrics.get('aiProcessingMinutes', 0)} min")
                with col2:
                    st.metric("Manual Estimate", f"{time_metrics.get('manualEstimateMinutes', 0)} min")
                with col3:
                    st.metric("Time Saved", 
                             f"{time_metrics.get('timeSavedMinutes', 0)} min",
                             delta=f"{time_metrics.get('timeSavedPercent', 0)}%")
                with col4:
                    st.metric("Cost Saved", 
                             f"${time_metrics.get('costSaved', 0)}",
                             delta=f"at ${time_metrics.get('hourlyRate', 23)}/hr")
        except:
            pass  # If no time metrics, just skip
    
    # Mode selector - UPDATED: Removed Timeline button, renamed Chain to Chain Analysis
    st.divider()
    mode_col1, mode_col2, mode_col3, mode_col4, mode_col5, mode_col6 = st.columns(6)
    
    with mode_col1:
        if st.button("👁️ View", use_container_width=True, 
                     type="primary" if st.session_state.view_mode == 'view' else "secondary"):
            st.session_state.view_mode = 'view'
            st.rerun()
    
    with mode_col2:
        if st.button("✏️ Edit", use_container_width=True,
                     type="primary" if st.session_state.view_mode == 'edit' else "secondary"):
            st.session_state.view_mode = 'edit'
            if abstract.is_edited and abstract.edited_json_data:
                st.session_state.working_json = json.loads(abstract.edited_json_data)
            else:
                st.session_state.working_json = json.loads(abstract.json_data)
            st.rerun()
    
    with mode_col3:
        if st.button("🔗 Chain Analysis", use_container_width=True,
                     type="primary" if st.session_state.view_mode == 'chain' else "secondary"):
            st.session_state.view_mode = 'chain'
            st.rerun()
    
    with mode_col4:
        if st.button("📄 PDF", use_container_width=True,
                     type="primary" if st.session_state.view_mode == 'pdf' else "secondary"):
            st.session_state.view_mode = 'pdf'
            st.rerun()
    
    with mode_col5:
        if st.button("💬 Chat", use_container_width=True,
                     type="primary" if st.session_state.view_mode == 'chat' else "secondary"):
            st.session_state.view_mode = 'chat'
            st.rerun()
    
    with mode_col6:
        if st.button("📋 Log", use_container_width=True,
                     type="primary" if st.session_state.view_mode == 'log' else "secondary"):
            st.session_state.view_mode = 'log'
            st.rerun()
    
    st.divider()
    
    # Content based on mode
    if st.session_state.view_mode == 'view':
        # VIEW MODE
        if abstract.is_edited and abstract.edited_markdown_output:
            st.markdown(abstract.edited_markdown_output)
        elif abstract.markdown_output:
            st.markdown(abstract.markdown_output)
        else:
            st.warning("No rendered output available")
        
        # Download buttons
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            data_to_download = abstract.edited_json_data if abstract.is_edited else abstract.json_data
            if data_to_download:
                st.download_button(
                    "📥 Download JSON",
                    data=data_to_download,
                    file_name=f"{abstract.filename}_abstract.json",
                    mime="application/json",
                    use_container_width=True
                )
        with col2:
            md_to_download = abstract.edited_markdown_output if abstract.is_edited else abstract.markdown_output
            if md_to_download:
                st.download_button(
                    "📥 Download Markdown",
                    data=md_to_download,
                    file_name=f"{abstract.filename}_abstract.md",
                    mime="text/markdown",
                    use_container_width=True
                )
    
    elif st.session_state.view_mode == 'edit':
        # EDIT MODE
        from modules.edit_interface import render_edit_interface
        render_edit_interface(abstract, db)
    
    elif st.session_state.view_mode == 'chain':
        # CHAIN ANALYSIS MODE - COMBINED Timeline and Chain Views
        try:
            data = json.loads(abstract.edited_json_data if abstract.is_edited else abstract.json_data)
        except:
            st.error("Could not load abstract data")
            data = None
        
        if data:
            st.subheader("🔗 Chain Analysis")
            
            # Create tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Timeline", "🗺️ Visual Chain", "📋 Chain Details", "🔍 Verification"])
            
            with tab1:
                # Timeline view
                from modules.timeline_view import render_timeline
                render_timeline(abstract)
            
            with tab2:
                # Visual chain diagram
                from modules.chain_visualization import render_chain_visualization
                render_chain_visualization(abstract)
            
            with tab3:
                # Chain details with related documents
                from modules.chain_detail_view import render_chain_detail_view
                render_chain_detail_view(abstract)
            
            with tab4:
                # Chain verification and analysis
                st.subheader("Chain Verification & Analysis")
                
                documents = data.get('documents', [])
                
                if not documents:
                    st.warning("No documents found to analyze.")
                else:
                    with st.spinner("Analyzing chain of title..."):
                        from src.relationship_detector import RelationshipDetector
                        from src.chain_builder import ChainBuilder
                        
                        # Phase 2: Detect relationships
                        detector = RelationshipDetector()
                        analysis = detector.analyze_all_documents(documents)
                        
                        # Phase 3: Build verified chains
                        builder = ChainBuilder()
                        result = builder.build_chains(analysis, documents)
                    
                    # Display summary
                    summary = result['summary']
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Chains", summary['total_chains'])
                    with col2:
                        st.metric("Verified Chains", summary['verified_chains'])
                    with col3:
                        st.metric("Total Documents", summary['total_documents'])
                    with col4:
                        if summary['total_issues'] == 0:
                            st.metric("Issues", "0", delta="✓")
                        else:
                            st.metric("Issues", summary['total_issues'], delta=f"-{summary['total_issues']}", delta_color="inverse")
                    
                    st.divider()
                    
                    # Display issues if any
                    if result['issues']:
                        st.error(f"⚠️ {len(result['issues'])} Issue(s) Detected")
                        
                        for i, issue in enumerate(result['issues'], 1):
                            severity_icon = "❌" if issue['severity'] == "CRITICAL" else "⚠️" if issue['severity'] == "WARNING" else "ℹ️"
                            with st.expander(f"{severity_icon} Issue #{i}: {issue['type']}", expanded=True):
                                st.write(issue['message'])
                        
                        st.divider()
                    else:
                        st.success("✅ No issues detected - all chains verified!")
                        st.divider()
                    
                    # Display hierarchy
                    st.subheader("Chain Hierarchy")
                    
                    def display_chain_node(node, level=0, indent=""):
                        """Display chain hierarchy without nested expanders"""
                        status_icon = "✅" if node['verified'] else "❌"
                        chain_name = node['chain_id'].replace('_', ' ').title()
                        
                        # Use indentation instead of nested expanders
                        if level == 0:
                            with st.expander(f"{status_icon} **{chain_name}** - {node['property']}", expanded=True):
                                st.write(f"**First Owner:** {node['first_owner']}")
                                st.write(f"**Documents:** {', '.join(f'#{d}' for d in node['document_ids'])}")
                                
                                if node['issues']:
                                    st.warning("**Issues:**")
                                    for issue in node['issues']:
                                        st.write(f"- {issue['message']}")
                                
                                if st.checkbox(f"Show document details", key=f"details_{node['chain_id']}_{level}"):
                                    for doc_id in node['document_ids']:
                                        doc = documents[doc_id - 1]
                                        st.markdown(f"""
                                        **Document #{doc_id}:** {doc.get('documentType', 'Unknown')}
                                        - Date: {doc.get('dates', {}).get('recordDate', 'Unknown')}
                                        - From: {', '.join(doc.get('parties', {}).get('from', ['Unknown']))}
                                        - To: {', '.join(doc.get('parties', {}).get('to', ['Unknown']))}
                                        - Recording: {doc.get('recording', {}).get('locationInstrumentNumber', 'Unknown')}
                                        """)
                                
                                # Display children with indentation
                                if node['children']:
                                    st.write("**Related Chains:**")
                                    for child in node['children']:
                                        display_chain_node(child, level + 1, indent + "  ")
                        else:
                            # Child nodes use markdown with indentation instead of expanders
                            child_icon = "✅" if node['verified'] else "❌"
                            st.markdown(f"{indent}**{child_icon} {chain_name}** - {node['property']}")
                            st.markdown(f"{indent}- First Owner: {node['first_owner']}")
                            st.markdown(f"{indent}- Documents: {', '.join(f'#{d}' for d in node['document_ids'])}")
                            
                            if node['issues']:
                                st.markdown(f"{indent}⚠️ Issues:")
                                for issue in node['issues']:
                                    st.markdown(f"{indent}  - {issue['message']}")
                            
                            # Recursively display deeper children
                            if node['children']:
                                for child in node['children']:
                                    display_chain_node(child, level + 1, indent + "  ")
                    
                    for node in result['hierarchy']:
                        display_chain_node(node)
    
    elif st.session_state.view_mode == 'pdf':
        # PDF VIEWER MODE
        from modules.pdf_viewer import render_pdf_viewer
        render_pdf_viewer(abstract, db)
    
    elif st.session_state.view_mode == 'chat':
        # CHATBOT MODE
        from modules.chatbot import render_chatbot
        render_chatbot(abstract, db, abstractor.gemini)
    
    elif st.session_state.view_mode == 'log':
        # PROCESSING LOG MODE
        st.subheader("📋 Processing History")
        
        if abstract.processing_log:
            # Parse log for statistics
            log_lines = abstract.processing_log.split('\n')
            error_count = sum(1 for line in log_lines if '[ERROR]' in line)
            warning_count = sum(1 for line in log_lines if '[WARNING]' in line)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Log Entries", len(log_lines))
            with col2:
                st.metric("Warnings", warning_count, delta="Issues" if warning_count > 0 else None)
            with col3:
                st.metric("Errors", error_count, delta="Critical" if error_count > 0 else None)
            
            st.divider()
            
            # Display log with syntax highlighting
            st.code(abstract.processing_log, language="log")
            
            # Download log button
            st.download_button(
                "📥 Download Processing Log",
                data=abstract.processing_log,
                file_name=f"{abstract.filename}_processing_log.txt",
                mime="text/plain",
                use_container_width=True
            )
        else:
            st.info("No processing log available for this abstract (processed before logging was implemented)")
