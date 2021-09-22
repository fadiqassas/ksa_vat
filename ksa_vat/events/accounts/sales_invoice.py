import frappe
from frappe import _
from erpnext import get_region
from pyqrcode import create as qr_create
import io
import os
import json


def after_insert(doc, method=None):
	create_qr_code(doc, method)

def validate(doc, method=None):
	create_item_consolidated_tax(doc)

def create_qr_code(doc, method):
	"""Create QR Code after inserting Sales Inv
	"""

	region = get_region(doc.company)
	if region not in ['Saudi Arabia']:
		return

	# if QR Code field not present, do nothing
	if not hasattr(doc, 'qr_code'):
		return

	# Don't create QR Code if it already exists
	qr_code = doc.get("qr_code")
	if qr_code and frappe.db.exists({"doctype": "File", "file_url": qr_code}):
		return

	fields = frappe.get_meta('Sales Invoice').fields
	
	for field in fields:
		if field.fieldname == 'qr_code' and field.fieldtype == 'Attach Image':
			# Creating public url to print format
			default_print_format = frappe.db.get_value('Property Setter', dict(property='default_print_format', doc_type=doc.doctype), "value")
			
			# System Language
			language = frappe.get_system_settings('language')
			
			# creating qr code for the url
			url = f"{ frappe.utils.get_url() }/{ doc.doctype }/{ doc.name }?format={ default_print_format or 'Standard' }&_lang={ language }&key={ doc.get_signature() }"
			qr_image = io.BytesIO()
			url = qr_create(url, error='L')
			url.png(qr_image, scale=2, quiet_zone=1)
			
			# making file
			filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__")
			_file = frappe.get_doc({
				"doctype": "File",
				"file_name": filename,
				"content": qr_image.getvalue(),
				"is_private": 1
			})

			_file.save()

			# assigning to document
			doc.db_set('qr_code', _file.file_url)
			doc.notify_update()

			break

		else:
			pass

def delete_qr_code_file(doc, method):
	"""Delete QR Code on deleted sales invoice"""
	
	region = get_region(doc.company)
	if region not in ['Saudi Arabia']:
		return

	if hasattr(doc, 'qr_code'):
		if doc.get('qr_code'):
			file_doc = frappe.get_list('File', {
				'file_url': doc.qr_code,
				'attached_to_doctype': doc.doctype,
				'attached_to_name': doc.name
			})
			if len(file_doc):
				frappe.delete_doc('File', file_doc[0].name)

def create_item_consolidated_tax(doc):
	taxes = doc.taxes
	consolidated_taxes = {}

	for row in taxes:
		item_wise_tax = row.item_wise_tax_detail
		item_wise_tax = json.loads(item_wise_tax)
		
		for key in item_wise_tax:
			item = item_wise_tax[key]
			if item[0] > 0:
				if key in consolidated_taxes:
					consolidated_taxes[key]["tax"] += item[0]
					consolidated_taxes[key]["amount"] += item[1]
				else:
					consolidated_taxes[key] = {
						"tax": item[0],
						"amount": item[1]
					}
				
	for key in consolidated_taxes:
		row = consolidated_taxes[key]
		doc.append("consolidated_item_taxes", {
			"item_code": key,
			"consolidated_tax_ratio": row["tax"],
			"consolidated_tax_amount": row["amount"],
		})