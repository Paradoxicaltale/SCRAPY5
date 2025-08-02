import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scrapy5.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Define the database model
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_type = db.Column(db.String(100))
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    quantity = db.Column(db.String(50))
    name = db.Column(db.String(100))
    location = db.Column(db.String(100))
    contact = db.Column(db.String(50))
    email = db.Column(db.String(100))
    photos = db.Column(db.Text)  # filenames joined by commas
    submission_date = db.Column(db.String(100))

@app.route('/')
def index():
    return render_template('index.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/submit_listing', methods=['POST'])
def submit_listing():
    print("🔔 /submit_listing triggered")
    try:
        # Extract form data
        material_type = request.form.get('materialType', '').strip()
        title = request.form.get('listingTitle', '').strip()
        description = request.form.get('listingDescription', '').strip()
        quantity = request.form.get('listingQuantity', '').strip()
        name = request.form.get('sellerName', '').strip()
        location = request.form.get('listingLocation', '').strip()
        contact = request.form.get('listingContact', '').strip()
        email = request.form.get('sellerEmail', '').strip()

        # Validate required fields
        required_fields = {
            'materialType': material_type,
            'listingTitle': title,
            'listingDescription': description,
            'listingQuantity': quantity,
            'sellerName': name,
            'listingLocation': location,
            'listingContact': contact,
            'sellerEmail': email
        }
        
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            return jsonify({
                'success': False, 
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            })

        # Handle multiple file uploads
        photo_files = request.files.getlist('fileInput')
        photo_filenames = []
        
        print(f"📁 Processing {len(photo_files)} files")
        
        for i, photo in enumerate(photo_files):
            if photo and photo.filename and photo.filename.strip():
                # Validate file type
                if not allowed_file(photo.filename):
                    print(f"❌ Invalid file type: {photo.filename}")
                    continue
                
                # Generate unique filename to prevent conflicts
                original_filename = secure_filename(photo.filename)
                name_part, ext_part = os.path.splitext(original_filename)
                unique_filename = f"{uuid.uuid4().hex[:8]}_{name_part}{ext_part}"
                
                # Save file
                try:
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    photo.save(save_path)
                    photo_filenames.append(unique_filename)
                    print(f"✅ Saved file {i+1}: {unique_filename}")
                except Exception as file_error:
                    print(f"❌ Error saving file {i+1}: {str(file_error)}")
                    continue
        
        print(f"📸 Successfully processed {len(photo_filenames)} photos")

        # Join photo filenames with commas
        photos = ','.join(photo_filenames) if photo_filenames else ''

        # Create new submission
        new_submission = Submission(
            material_type=material_type,
            title=title,
            description=description,
            quantity=quantity,
            name=name,
            location=location,
            contact=contact,
            email=email,
            photos=photos,
            submission_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        print(f"💾 Saving submission with title: {title}")
        print(f"📊 Photos saved: {len(photo_filenames)}")
        
        # Save to database
        db.session.add(new_submission)
        db.session.commit()
        
        success_message = f'Listing submitted successfully! '
        if len(photo_filenames) > 0:
            success_message += f'{len(photo_filenames)} photo(s) uploaded.'
        else:
            success_message += 'No photos uploaded.'

        return jsonify({
            'success': True, 
            'message': success_message,
            'photos_uploaded': len(photo_filenames),
            'submission_id': new_submission.id
        })

    except Exception as e:
        import traceback
        print("💥 Error in submit_listing:")
        traceback.print_exc()
        
        return jsonify({
            'success': False, 
            'message': f'Failed to submit listing. Error: {str(e)}'
        })

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        print(f"❌ Error serving file {filename}: {str(e)}")
        return "File not found", 404

@app.route('/admin/submissions')
def view_submissions():
    """Admin route to view all submissions"""
    try:
        submissions = Submission.query.order_by(Submission.id.desc()).all()
        submissions_data = []
        
        for submission in submissions:
            photo_list = submission.photos.split(',') if submission.photos else []
            submissions_data.append({
                'id': submission.id,
                'material_type': submission.material_type,
                'title': submission.title,
                'description': submission.description,
                'quantity': submission.quantity,
                'name': submission.name,
                'location': submission.location,
                'contact': submission.contact,
                'email': submission.email,
                'photos': photo_list,
                'submission_date': submission.submission_date
            })
        
        return jsonify({
            'success': True,
            'submissions': submissions_data,
            'total': len(submissions_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching submissions: {str(e)}'
        })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'database': 'connected'
    })

if __name__ == '__main__':
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Check if upload directory exists
            if os.path.exists(app.config['UPLOAD_FOLDER']):
                print(f"✅ Upload directory exists: {app.config['UPLOAD_FOLDER']}")
            else:
                print(f"❌ Upload directory missing: {app.config['UPLOAD_FOLDER']}")
                
        except Exception as e:
            print(f"❌ Database initialization error: {str(e)}")
    
    print("🚀 Starting Scrapy5 server...")
    print("📁 Upload folder:", app.config['UPLOAD_FOLDER'])
    print("💾 Database:", app.config['SQLALCHEMY_DATABASE_URI'])
    print("🌐 Server will be available at: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)