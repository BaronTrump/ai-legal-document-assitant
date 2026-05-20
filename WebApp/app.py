from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
import sys
import json
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'APIs'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Templates'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Generated'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'APIs', '.env'))

from document_engine import DocumentGenerationEngine
from citation_verifier import CitationVerifier

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'

# Configuration
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'Templates')
GENERATED_DIR = os.path.join(os.path.dirname(__file__), '..', 'Generated')

# Available states and document types
STATE_OPTIONS = {
    'AL': 'Alabama',
    'CA': 'California', 
    'TX': 'Texas',
    'NY': 'New York',
    'FL': 'Florida',
    'IL': 'Illinois'
}

DOC_TYPE_OPTIONS = {
    'complaint': 'Complaint / Petition',
    'petition': 'Petition',
    'answer': 'Answer / Response',
    'motion': 'Motion to Dismiss',
    'financial': 'Financial Affidavit',
    'subpoena': 'Subpoena',
    'interrogatories': 'Interrogatories',
    'document_requests': 'Document Requests',
    'tro': 'Temporary Restraining Order',
    'default_judgment': 'Default Judgment',
    'appearance': 'Entry of Appearance',
    'notice_of_hearing': 'Notice of Hearing'
}

PRICING_TIERS = [
    {
        'name': 'Free',
        'price': 0,
        'price_display': 'Free',
        'features': [
            '1 document per month',
            'Basic legal research (5 queries)',
            'CourtListener verification (5 checks)',
            'Access to CA templates only'
        ],
        'cta': 'Get Started',
        'highlight': False
    },
    {
        'name': 'Basic',
        'price': 5,
        'price_display': '$5/mo',
        'features': [
            '5 documents per month',
            'Full legal research access',
            'Unlimited citation verification',
            'All 6 state templates',
            'Document version history'
        ],
        'cta': 'Start Basic',
        'highlight': False
    },
    {
        'name': 'Pro',
        'price': 49,
        'price_display': '$49/mo',
        'features': [
            'Unlimited documents',
            'Priority AI models (Claude, GPT-4)',
            'Judge profiling & docket alerts',
            'No-code workflow builder',
            'Document comparison tool',
            'Email support'
        ],
        'cta': 'Go Pro',
        'highlight': True
    },
    {
        'name': 'Enterprise',
        'price': 149,
        'price_display': '$149/mo',
        'features': [
            'Everything in Pro',
            'Multi-user accounts',
            'Custom workflow templates',
            'API access for firms',
            'Docket Alarm integration',
            'Phone & priority support'
        ],
        'cta': 'Contact Sales',
        'highlight': False
    }
]


@app.route('/')
def landing():
    return render_template('landing.html', pricing_tiers=PRICING_TIERS)


@app.route('/pricing')
def pricing():
    return render_template('pricing.html', pricing_tiers=PRICING_TIERS)


@app.route('/dashboard')
def dashboard():
    # List generated documents
    docs = []
    if os.path.exists(GENERATED_DIR):
        for f in os.listdir(GENERATED_DIR):
            if f.endswith('.md') or f.endswith('.txt'):
                filepath = os.path.join(GENERATED_DIR, f)
                stat = os.stat(filepath)
                docs.append({
                    'name': f,
                    'date': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M'),
                    'size': f'{stat.st_size / 1024:.1f} KB'
                })
    return render_template('dashboard.html', docs=docs, states=STATE_OPTIONS)


@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        state = request.form.get('state')
        doc_type = request.form.get('doc_type')
        
        # Parse facts from form
        facts = {}
        for key, value in request.form.items():
            if key.startswith('fact_') and value:
                facts[key.replace('fact_', '').upper()] = value
        
        # Generate document
        try:
            engine = DocumentGenerationEngine()
            result = engine.generate(state, doc_type, facts)
            engine.print_summary(result)
            
            # Save result
            output_path = os.path.join(GENERATED_DIR, f"{state}_{doc_type}_{facts.get('CASE_NUMBER', 'untitled')}.md")
            engine.save_document(result['document'], output_path)
            
            return jsonify({
                'success': True,
                'document': result['document'][:2000] + '...' if len(result['document']) > 2000 else result['document'],
                'fields_filled': len(result['template_fields']) - len(result['missing_fields']),
                'total_fields': len(result['template_fields']),
                'missing_fields': result['missing_fields'],
                'warnings': result['warnings'],
                'download_url': f'/download/{os.path.basename(output_path)}'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return render_template('generate.html', states=STATE_OPTIONS, doc_types=DOC_TYPE_OPTIONS)


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        text = request.form.get('text', '')
        try:
            verifier = CitationVerifier()
            result = verifier.verify_text(text)
            report = verifier.generate_report(result)
            return jsonify({
                'success': True,
                'total': result['total_citations'],
                'verified': len(result['verified']),
                'hallucinated': len(result['hallucinated']),
                'rate': f"{result['verification_rate']*100:.1f}%",
                'verified_list': result['verified'],
                'hallucinated_list': result['hallucinated'],
                'report': report
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return render_template('verify.html')


@app.route('/workflow')
def workflow():
    return render_template('workflow.html')


@app.route('/templates')
def templates():
    # List available templates
    templates_list = []
    if os.path.exists(TEMPLATES_DIR):
        for f in sorted(os.listdir(TEMPLATES_DIR)):
            if f.endswith('.md'):
                # Parse state and type from filename
                parts = f.replace('.md', '').split('_')
                if len(parts) >= 2:
                    state = parts[0].upper()
                    doc_type = '_'.join(parts[1:])
                    templates_list.append({
                        'filename': f,
                        'state': STATE_OPTIONS.get(state, state),
                        'state_code': state,
                        'doc_type': doc_type.replace('_', ' ').title(),
                        'view_url': f'/template/view/{f}',
                        'download_url': f'/template/download/{f}'
                    })
    return render_template('templates.html', templates=templates_list, states=STATE_OPTIONS)


@app.route('/template/view/<filename>')
def view_template(filename):
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        return render_template('view_template.html', filename=filename, content=content)
    return "Template not found", 404


@app.route('/template/download/<filename>')
def download_template(filename):
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return "Template not found", 404


@app.route('/download/<filename>')
def download_document(filename):
    filepath = os.path.join(GENERATED_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return "Document not found", 404


@app.route('/api/generate', methods=['POST'])
def api_generate():
    """API endpoint for document generation."""
    data = request.get_json()
    state = data.get('state')
    doc_type = data.get('doc_type')
    facts = data.get('facts', {})
    
    try:
        engine = DocumentGenerationEngine()
        result = engine.generate(state, doc_type, facts)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/verify', methods=['POST'])
def api_verify():
    """API endpoint for citation verification."""
    data = request.get_json()
    text = data.get('text', '')
    
    try:
        verifier = CitationVerifier()
        result = verifier.verify_text(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/case')
def case_browser():
    """Browse case files and folders"""
    case_path = "/media/cyber/DEV1/DOCUMENTS/work comp"
    rel_path = request.args.get('path', '')
    
    if rel_path:
        current_path = os.path.join(case_path, rel_path)
    else:
        current_path = case_path
    
    items = []
    if os.path.exists(current_path):
        for item in sorted(os.listdir(current_path)):
            full_path = os.path.join(current_path, item)
            is_dir = os.path.isdir(full_path)
            rel_item_path = os.path.join(rel_path, item) if rel_path else item
            items.append({
                'name': item,
                'path': rel_item_path,
                'is_dir': is_dir,
                'size': os.path.getsize(full_path) if not is_dir else 0
            })
    
    return render_template('case_browser.html', 
                         items=items, 
                         current_path=rel_path or '/',
                         case_number='CV-26-00008')

@app.route('/case/view')
def case_view():
    """View a specific case file"""
    file_path = request.args.get('file', '')
    full_path = os.path.join("/media/cyber/DEV1/DOCUMENTS/work comp", file_path)
    
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return "File not found", 404
    
    # Read file content (handle text files)
    try:
        if full_path.endswith(('.txt', '.md', '.csv', '.json')):
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return render_template('case_view.html', 
                             filename=os.path.basename(file_path),
                             content=content,
                             file_path=file_path)
        else:
            return send_file(full_path, as_attachment=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
