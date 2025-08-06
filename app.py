import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_cgE2x3TezlId@ep-lucky-term-a1mcewu3-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Define the database models
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

# New Price model for managing scrap prices
class ScrapPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # kg, piece, etc.
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('category', 'subcategory'),)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    """Serve the admin panel"""
    return render_template('admin.html')

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

# ========== ADMIN ENDPOINTS ==========

@app.route('/admin/submissions')
def view_submissions():
    """Admin route to view all submissions with search and filter support"""
    try:
        # Get query parameters
        search = request.args.get('search', '').strip()
        material_filter = request.args.get('material', '').strip()
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Build query
        query = Submission.query
        
        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                db.or_(
                    Submission.material_type.ilike(search_pattern),
                    Submission.title.ilike(search_pattern),
                    Submission.description.ilike(search_pattern),
                    Submission.name.ilike(search_pattern),
                    Submission.location.ilike(search_pattern),
                    Submission.contact.ilike(search_pattern),
                    Submission.email.ilike(search_pattern)
                )
            )
        
        # Apply material filter
        if material_filter:
            query = query.filter(Submission.material_type.ilike(f"%{material_filter}%"))
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply ordering, limit and offset
        submissions = query.order_by(Submission.id.desc()).limit(limit).offset(offset).all()
        
        submissions_data = []
        
        for submission in submissions:
            # Convert photo filenames to proper URLs
            photo_list = []
            if submission.photos:
                photo_list = [
                    f"/uploads/{fname.strip()}"
                    for fname in submission.photos.split(',')
                    if fname.strip()
                ]
            
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
                'photo_count': len(photo_list),
                'submission_date': submission.submission_date
            })
        
        return jsonify({
            'success': True,
            'submissions': submissions_data,
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching submissions: {str(e)}'
        })

@app.route('/admin/dashboard-stats')
def dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Total submissions
        total_submissions = Submission.query.count()
        
        # Material types count
        material_types = db.session.query(Submission.material_type).distinct().count()
        
        # Total images count
        total_images = 0
        submissions_with_photos = Submission.query.filter(Submission.photos.isnot(None), Submission.photos != '').all()
        for submission in submissions_with_photos:
            if submission.photos:
                photo_count = len([p for p in submission.photos.split(',') if p.strip()])
                total_images += photo_count
        
        # Today's submissions
        today = datetime.now().strftime('%Y-%m-%d')
        today_submissions = Submission.query.filter(
            Submission.submission_date.like(f"{today}%")
        ).count()
        
        # Average photos per listing
        avg_photos = round(total_images / max(total_submissions, 1), 1)
        
        # Recent submissions (last 5)
        recent_submissions = Submission.query.order_by(Submission.id.desc()).limit(5).all()
        recent_data = []
        
        for submission in recent_submissions:
            photo_list = []
            if submission.photos:
                photo_list = [
                    f"/uploads/{fname.strip()}"
                    for fname in submission.photos.split(',')
                    if fname.strip()
                ]
            
            recent_data.append({
                'id': submission.id,
                'material_type': submission.material_type,
                'title': submission.title,
                'description': submission.description[:100] + '...' if len(submission.description) > 100 else submission.description,
                'name': submission.name,
                'location': submission.location,
                'photos': photo_list[:3],  # Only first 3 photos for dashboard
                'submission_date': submission.submission_date
            })
        
        return jsonify({
            'success': True,
            'stats': {
                'total_submissions': total_submissions,
                'material_types': material_types,
                'total_images': total_images,
                'today_submissions': today_submissions,
                'avg_photos': avg_photos
            },
            'recent_submissions': recent_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching dashboard stats: {str(e)}'
        })

@app.route('/admin/submission/<int:submission_id>')
def get_submission(submission_id):
    """Get detailed information about a specific submission"""
    try:
        submission = Submission.query.get_or_404(submission_id)
        
        # Convert photo filenames to proper URLs
        photo_list = []
        if submission.photos:
            photo_list = [
                f"/uploads/{fname.strip()}"
                for fname in submission.photos.split(',')
                if fname.strip()
            ]
        
        submission_data = {
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
        }
        
        return jsonify({
            'success': True,
            'submission': submission_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching submission: {str(e)}'
        })

@app.route('/admin/submission/<int:submission_id>', methods=['DELETE'])
def delete_submission(submission_id):
    """Delete a submission and its associated files"""
    try:
        submission = Submission.query.get_or_404(submission_id)
        
        # Delete associated files
        if submission.photos:
            photo_files = [fname.strip() for fname in submission.photos.split(',') if fname.strip()]
            for filename in photo_files:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"✅ Deleted file: {filename}")
                except Exception as file_error:
                    print(f"❌ Error deleting file {filename}: {str(file_error)}")
        
        # Delete from database
        db.session.delete(submission)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Submission "{submission.title}" deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting submission: {str(e)}'
        })

# ========== PRICING ENDPOINTS ==========

@app.route('/admin/prices')
def get_prices():
    """Get all current scrap prices"""
    try:
        prices = ScrapPrice.query.all()
        price_data = {}
        
        for price in prices:
            if price.category not in price_data:
                price_data[price.category] = {}
            price_data[price.category][price.subcategory] = {
                'price': price.price,
                'unit': price.unit,
                'last_updated': price.last_updated.isoformat()
            }
        
        return jsonify({
            'success': True,
            'prices': price_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching prices: {str(e)}'
        })

@app.route('/admin/prices', methods=['POST'])
def update_prices():
    """Update scrap prices"""
    try:
        price_updates = request.json.get('prices', {})
        
        updated_count = 0
        for category, subcategories in price_updates.items():
            for subcategory, price_info in subcategories.items():
                price = price_info.get('price')
                unit = price_info.get('unit', 'kg')
                
                if price is not None and price >= 0:
                    # Find existing price or create new one
                    existing_price = ScrapPrice.query.filter_by(
                        category=category, 
                        subcategory=subcategory
                    ).first()
                    
                    if existing_price:
                        existing_price.price = price
                        existing_price.unit = unit
                        existing_price.last_updated = datetime.utcnow()
                    else:
                        new_price = ScrapPrice(
                            category=category,
                            subcategory=subcategory,
                            price=price,
                            unit=unit
                        )
                        db.session.add(new_price)
                    
                    updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated {updated_count} prices',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating prices: {str(e)}'
        })

@app.route('/admin/prices/initialize', methods=['POST'])
def initialize_default_prices():
    """Initialize default prices for all categories"""
    try:
        default_prices = [
            # Metal Scrap
            ('metal', 'iron', 25.0, 'kg'),
            ('metal', 'copper', 650.0, 'kg'),
            ('metal', 'aluminum', 150.0, 'kg'),
            
            # Electronics
            ('electronics', 'smartphones', 500.0, 'piece'),
            ('electronics', 'laptops', 2000.0, 'piece'),
            ('electronics', 'components', 120.0, 'kg'),
            
            # Paper & Cardboard
            ('paper', 'newspapers', 8.0, 'kg'),
            ('paper', 'books', 12.0, 'kg'),
            ('paper', 'cardboard', 6.0, 'kg'),
            
            # Plastic
            ('plastic', 'pet', 20.0, 'kg'),
            ('plastic', 'containers', 15.0, 'kg'),
            ('plastic', 'mixed-plastic', 10.0, 'kg'),
            
            # Automotive
            ('automotive', 'batteries', 180.0, 'piece'),
            ('automotive', 'tires', 50.0, 'piece'),
            ('automotive', 'auto-parts', 30.0, 'kg'),
            
            # Construction
            ('construction', 'steel', 40.0, 'kg'),
            ('construction', 'concrete', 2.0, 'kg'),
        ]
        
        added_count = 0
        for category, subcategory, price, unit in default_prices:
            existing = ScrapPrice.query.filter_by(
                category=category, 
                subcategory=subcategory
            ).first()
            
            if not existing:
                new_price = ScrapPrice(
                    category=category,
                    subcategory=subcategory,
                    price=price,
                    unit=unit
                )
                db.session.add(new_price)
                added_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Initialized {added_count} default prices',
            'added_count': added_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error initializing prices: {str(e)}'
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
    print("🔧 Admin panel will be available at: http://localhost:5000/admin")
    print("\n📋 Available Admin API Endpoints:")
    print("   GET  /admin/submissions - View all submissions with search/filter")
    print("   GET  /admin/dashboard-stats - Dashboard statistics")
    print("   GET  /admin/submission/<id> - Get specific submission")
    print("   DEL  /admin/submission/<id> - Delete submission")
    print("   GET  /admin/prices - Get all prices")
    print("   POST /admin/prices - Update prices")
    print("   POST /admin/prices/initialize - Initialize default prices")
    
    app.run(host='0.0.0.0', port=5000, debug=True)