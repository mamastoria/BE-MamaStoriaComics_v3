"""
Generate PDF documentation for MamaStoria Infrastructure Configuration
"""

from fpdf import FPDF
from datetime import datetime

class InfrastructurePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'MamaStoria Infrastructure Configuration', align='C', ln=True)
        self.set_font('Helvetica', '', 8)
        self.cell(0, 5, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', align='C', ln=True)
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    def section_title(self, title):
        self.set_font('Helvetica', 'B', 14)
        self.set_fill_color(52, 73, 94)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, title, fill=True, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(3)
    
    def sub_title(self, title):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(41, 128, 185)
        self.cell(0, 8, title, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)
    
    def table_row(self, col1, col2, header=False):
        self.set_font('Helvetica', 'B' if header else '', 9)
        if header:
            self.set_fill_color(236, 240, 241)
        else:
            self.set_fill_color(255, 255, 255)
        self.cell(70, 7, col1, border=1, fill=True)
        self.cell(0, 7, col2, border=1, fill=True, ln=True)
    
    def add_text(self, text):
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 6, text)
        self.ln(2)


def generate_pdf():
    pdf = InfrastructurePDF()
    pdf.add_page()
    
    # Title
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 15, 'MamaStoria', align='C', ln=True)
    pdf.set_font('Helvetica', '', 14)
    pdf.cell(0, 10, 'Cloud Infrastructure Configuration', align='C', ln=True)
    pdf.ln(10)
    
    # Overview
    pdf.section_title('1. Overview')
    pdf.add_text(
        'This document contains the current cloud infrastructure configuration for '
        'MamaStoria application deployed on Google Cloud Platform (GCP). '
        'The application uses Cloud Run for containerized services, Cloud SQL for database, '
        'and Cloud Storage for media files.'
    )
    pdf.ln(5)
    
    # Cloud Run Services
    pdf.section_title('2. Cloud Run Services')
    
    # Backend
    pdf.sub_title('2.1 nanobanana-backend (Main API)')
    pdf.table_row('Parameter', 'Value', header=True)
    pdf.table_row('Service Name', 'nanobanana-backend')
    pdf.table_row('Region', 'asia-southeast2 (Jakarta)')
    pdf.table_row('URL', 'https://nanobanana-backend-...run.app')
    pdf.table_row('CPU', '4 vCPU')
    pdf.table_row('Memory', '4 GB')
    pdf.table_row('Concurrency', '100 requests/instance')
    pdf.table_row('Min Instances', '2 (always warm)')
    pdf.table_row('Max Instances', '50')
    pdf.table_row('Timeout', '300 seconds')
    pdf.table_row('CPU Throttling', 'Disabled')
    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(39, 174, 96)
    pdf.cell(0, 7, 'Capacity: 50 x 100 = 5,000 concurrent requests', ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    # Worker
    pdf.sub_title('2.2 nanobanana-worker (Background Jobs)')
    pdf.table_row('Parameter', 'Value', header=True)
    pdf.table_row('Service Name', 'nanobanana-worker')
    pdf.table_row('Region', 'asia-southeast2 (Jakarta)')
    pdf.table_row('CPU', '2 vCPU')
    pdf.table_row('Memory', '4 GB')
    pdf.table_row('Concurrency', '1 request/instance')
    pdf.table_row('Max Instances', '50')
    pdf.table_row('Purpose', 'Long-running comic generation')
    pdf.ln(5)
    
    # Smart Crop
    pdf.sub_title('2.3 smart-crop-worker (OpenCV Cropping)')
    pdf.table_row('Parameter', 'Value', header=True)
    pdf.table_row('Service Name', 'smart-crop-worker')
    pdf.table_row('Type', 'Cloud Functions Gen2')
    pdf.table_row('Region', 'asia-southeast2 (Jakarta)')
    pdf.table_row('CPU', '1 vCPU')
    pdf.table_row('Memory', '2 GB')
    pdf.table_row('Concurrency', '10 requests/instance')
    pdf.table_row('Max Instances', '100')
    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(39, 174, 96)
    pdf.cell(0, 7, 'Capacity: 100 x 10 = 1,000 concurrent crops', ln=True)
    pdf.set_text_color(0, 0, 0)
    
    # New page for Database & Storage
    pdf.add_page()
    
    # Database
    pdf.section_title('3. Database Configuration')
    pdf.sub_title('Cloud SQL (PostgreSQL)')
    pdf.table_row('Parameter', 'Value', header=True)
    pdf.table_row('Instance Name', 'cloudsql-nanobanana-dev')
    pdf.table_row('Region', 'asia-southeast2')
    pdf.table_row('Type', 'PostgreSQL')
    pdf.table_row('Connection', 'Cloud SQL Connector')
    pdf.ln(5)
    
    # Storage
    pdf.section_title('4. Storage Configuration')
    pdf.sub_title('Google Cloud Storage')
    pdf.table_row('Parameter', 'Value', header=True)
    pdf.table_row('Bucket Name', 'mamastoria-storage')
    pdf.table_row('Region', 'asia-southeast2')
    pdf.table_row('Access', 'Public (comic assets)')
    pdf.ln(5)
    
    pdf.add_text('Storage Paths:')
    pdf.set_font('Courier', '', 9)
    pdf.multi_cell(0, 5, 
        '  comics/panels/{comic_id}/   - Panel images\n'
        '  comics/videos/{comic_id}/   - Generated videos\n'
        '  comics/grids/{comic_id}/    - Full grid images\n'
        '  users/avatars/              - User profile pictures'
    )
    pdf.ln(5)
    
    # External Services
    pdf.section_title('5. External Services')
    
    pdf.sub_title('Google Cloud Text-to-Speech')
    pdf.table_row('Parameter', 'Value', header=True)
    pdf.table_row('Voice', 'id-ID-Wavenet-A')
    pdf.table_row('Language', 'Indonesian (id-ID)')
    pdf.table_row('Gender', 'Female')
    pdf.table_row('Speaking Rate', '0.9')
    pdf.ln(5)
    
    pdf.sub_title('Vertex AI (Image Generation)')
    pdf.table_row('Parameter', 'Value', header=True)
    pdf.table_row('Location', 'us-central1')
    pdf.table_row('Model', 'imagen-3.0-generate-002')
    pdf.ln(5)
    
    # Capacity Summary
    pdf.add_page()
    pdf.section_title('6. Capacity Summary')
    
    pdf.sub_title('For 1,000 Concurrent Users')
    pdf.table_row('Service', 'Capacity', header=True)
    pdf.table_row('API Requests', '5,000 concurrent - SUFFICIENT')
    pdf.table_row('Panel Cropping', '1,000 concurrent - SUFFICIENT')
    pdf.table_row('Comic Generation', '50 concurrent - SUFFICIENT')
    pdf.ln(5)
    
    pdf.sub_title('Response Times (P95)')
    pdf.table_row('Endpoint', 'Latency', header=True)
    pdf.table_row('List Comics', '< 150ms')
    pdf.table_row('Comic Detail', '< 130ms')
    pdf.table_row('Comic Panels', '< 120ms')
    pdf.table_row('List Styles', '< 250ms')
    pdf.table_row('List Genres', '< 125ms')
    pdf.ln(5)
    
    # Cost Estimation
    pdf.section_title('7. Cost Estimation (Monthly)')
    pdf.table_row('Service', 'Est. Cost', header=True)
    pdf.table_row('Cloud Run (backend, 2 min instances)', '~$50/month')
    pdf.table_row('Cloud Run (worker, pay per use)', '~$20/month')
    pdf.table_row('Cloud Functions (pay per use)', '~$10/month')
    pdf.table_row('Cloud SQL (db-f1-micro)', '~$10/month')
    pdf.table_row('Cloud Storage (~50GB)', '~$5/month')
    pdf.table_row('Vertex AI (per image)', 'Variable')
    pdf.table_row('Text-to-Speech (per character)', 'Variable')
    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 7, 'Base Infrastructure: ~$95/month (excluding AI usage)', ln=True)
    pdf.ln(5)
    
    # Project Info
    pdf.section_title('8. Project Information')
    pdf.table_row('Field', 'Value', header=True)
    pdf.table_row('Project ID', 'nanobananacomic-482111')
    pdf.table_row('Primary Region', 'asia-southeast2 (Jakarta)')
    pdf.table_row('Document Version', '1.0')
    pdf.table_row('Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # Save
    output_path = 'docs/MamaStoria_Infrastructure_Config.pdf'
    pdf.output(output_path)
    print(f'PDF generated: {output_path}')
    return output_path


if __name__ == '__main__':
    generate_pdf()
