"""
ThreadOS Backend API Test Suite
Tests all API endpoints with demo credentials
"""
import requests
import sys
from datetime import datetime

class ThreadOSAPITester:
    def __init__(self, base_url="https://inventory-intel-14.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, check_response=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Test {self.tests_run}: {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                print(f"❌ Failed - Unsupported method {method}")
                self.failed_tests.append({"test": name, "reason": f"Unsupported method {method}"})
                return False, {}

            success = response.status_code == expected_status
            if success:
                try:
                    response_data = response.json()
                    # Additional response validation if provided
                    if check_response and not check_response(response_data):
                        print(f"❌ Failed - Response validation failed")
                        self.failed_tests.append({"test": name, "reason": "Response validation failed", "response": response_data})
                        return False, response_data
                    self.tests_passed += 1
                    print(f"✅ Passed - Status: {response.status_code}")
                    return True, response_data
                except Exception as e:
                    print(f"❌ Failed - JSON parse error: {str(e)}")
                    self.failed_tests.append({"test": name, "reason": f"JSON parse error: {str(e)}"})
                    return False, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error detail: {error_detail}")
                    self.failed_tests.append({"test": name, "reason": f"Status {response.status_code}", "detail": error_detail})
                except:
                    self.failed_tests.append({"test": name, "reason": f"Status {response.status_code}"})
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            self.failed_tests.append({"test": name, "reason": "Request timeout"})
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({"test": name, "reason": str(e)})
            return False, {}

    def test_login_success(self):
        """Test login with correct demo credentials"""
        success, response = self.run_test(
            "Login with demo@threados.com / demo1234",
            "POST",
            "auth/login",
            200,
            data={"email": "demo@threados.com", "password": "demo1234"},
            check_response=lambda r: 'access_token' in r and 'user' in r
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            print(f"   ✓ Token acquired: {self.token[:20]}...")
            print(f"   ✓ User: {response['user'].get('email')}, Brand: {response['user'].get('brand')}")
            return True
        return False

    def test_login_failure(self):
        """Test login with wrong password"""
        success, response = self.run_test(
            "Login with wrong password",
            "POST",
            "auth/login",
            401,
            data={"email": "demo@threados.com", "password": "wrongpassword"}
        )
        return success

    def test_auth_me(self):
        """Test GET /api/auth/me with bearer token"""
        success, response = self.run_test(
            "GET /api/auth/me (requires bearer token)",
            "GET",
            "auth/me",
            200,
            check_response=lambda r: 'email' in r and r['email'] == 'demo@threados.com'
        )
        if success:
            print(f"   ✓ User info: {response}")
        return success

    def test_dashboard_summary(self):
        """Test GET /api/dashboard/summary"""
        success, response = self.run_test(
            "GET /api/dashboard/summary",
            "GET",
            "dashboard/summary",
            200,
            check_response=lambda r: all(k in r for k in ['kpis', 'risk_counts', 'best_sellers', 'slow_movers', 'low_stock_alerts', 'recent_sales'])
        )
        if success:
            kpis = response.get('kpis', {})
            print(f"   ✓ Total units: {kpis.get('total_units')}")
            print(f"   ✓ Inventory value (retail): £{kpis.get('inventory_value_retail')}")
            print(f"   ✓ Days of stock: {kpis.get('days_of_stock')}")
            print(f"   ✓ Low stock count: {kpis.get('low_stock_count')}")
            print(f"   ✓ SKU count: {kpis.get('sku_count')}")
            print(f"   ✓ Revenue 30d: £{kpis.get('revenue_30d')}")
            print(f"   ✓ Best sellers count: {len(response.get('best_sellers', []))}")
            print(f"   ✓ Slow movers count: {len(response.get('slow_movers', []))}")
            print(f"   ✓ Low stock alerts: {len(response.get('low_stock_alerts', []))}")
            print(f"   ✓ Recent sales days: {len(response.get('recent_sales', []))}")
        return success

    def test_products_list(self):
        """Test GET /api/products"""
        success, response = self.run_test(
            "GET /api/products",
            "GET",
            "products",
            200,
            check_response=lambda r: 'items' in r and 'categories' in r and len(r['items']) > 0
        )
        if success:
            print(f"   ✓ Total items: {response.get('total')}")
            print(f"   ✓ Categories: {response.get('categories')}")
            # Test filters
            if response.get('items'):
                first_item = response['items'][0]
                print(f"   ✓ First item: {first_item.get('sku_id')} - {first_item.get('name')}")
        return success

    def test_products_filters(self):
        """Test GET /api/products with filters"""
        # Test category filter
        success1, response1 = self.run_test(
            "GET /api/products?category=Tops",
            "GET",
            "products?category=Tops",
            200,
            check_response=lambda r: all(i['category'] == 'Tops' for i in r.get('items', []))
        )
        
        # Test risk filter
        success2, response2 = self.run_test(
            "GET /api/products?risk=high_stockout",
            "GET",
            "products?risk=high_stockout",
            200,
            check_response=lambda r: all(i['bucket'] == 'high_stockout' for i in r.get('items', []))
        )
        
        # Test search
        success3, response3 = self.run_test(
            "GET /api/products?q=Cotton",
            "GET",
            "products?q=Cotton",
            200,
            check_response=lambda r: 'items' in r
        )
        
        return success1 and success2 and success3

    def test_product_detail(self):
        """Test GET /api/products/SKU-0001"""
        success, response = self.run_test(
            "GET /api/products/SKU-0001",
            "GET",
            "products/SKU-0001",
            200,
            check_response=lambda r: all(k in r for k in ['sku', 'forecast', 'recommendation', 'risk', 'sales_history'])
        )
        if success:
            print(f"   ✓ SKU: {response['sku'].get('id')} - {response['sku'].get('name')}")
            print(f"   ✓ Current stock: {response['sku'].get('current_stock')}")
            print(f"   ✓ Forecast 30d: {response['forecast'].get('forecast_30')}")
            print(f"   ✓ Forecast 60d: {response['forecast'].get('forecast_60')}")
            print(f"   ✓ Forecast 90d: {response['forecast'].get('forecast_90')}")
            print(f"   ✓ Confidence: {response['forecast'].get('confidence')}%")
            print(f"   ✓ Recommended qty: {response['recommendation'].get('recommended_qty')}")
            print(f"   ✓ Reorder by: {response['recommendation'].get('reorder_by_date')}")
            print(f"   ✓ Risk bucket: {response['risk'].get('bucket')}")
            print(f"   ✓ Sales history entries: {len(response.get('sales_history', []))} (should be 90)")
            print(f"   ✓ Units 30d: {response.get('units_30d')}")
            print(f"   ✓ Revenue 30d: £{response.get('revenue_30d')}")
        return success

    def test_sales_history(self):
        """Test GET /api/products/SKU-0001/sales-history"""
        success, response = self.run_test(
            "GET /api/products/SKU-0001/sales-history",
            "GET",
            "products/SKU-0001/sales-history",
            200,
            check_response=lambda r: 'history' in r and len(r['history']) == 90
        )
        if success:
            print(f"   ✓ History entries: {len(response.get('history', []))}")
        return success

    def test_forecast(self):
        """Test GET /api/products/SKU-0001/forecast"""
        success, response = self.run_test(
            "GET /api/products/SKU-0001/forecast",
            "GET",
            "products/SKU-0001/forecast",
            200,
            check_response=lambda r: 'forecast' in r and all(k in r['forecast'] for k in ['forecast_30', 'forecast_60', 'forecast_90', 'confidence'])
        )
        if success:
            fc = response.get('forecast', {})
            print(f"   ✓ Forecast: 30d={fc.get('forecast_30')}, 60d={fc.get('forecast_60')}, 90d={fc.get('forecast_90')}, confidence={fc.get('confidence')}%")
        return success

    def test_recommendations(self):
        """Test GET /api/recommendations"""
        success, response = self.run_test(
            "GET /api/recommendations",
            "GET",
            "recommendations",
            200,
            check_response=lambda r: 'items' in r and 'total_order_cost' in r and 'total_order_units' in r
        )
        if success:
            print(f"   ✓ Actionable items (recommended_qty > 0): {len(response.get('items', []))}")
            print(f"   ✓ Total order cost: £{response.get('total_order_cost')}")
            print(f"   ✓ Total order units: {response.get('total_order_units')}")
            # Check items are sorted by qty desc
            items = response.get('items', [])
            if len(items) > 1:
                sorted_check = all(items[i]['recommended_qty'] >= items[i+1]['recommended_qty'] for i in range(len(items)-1))
                print(f"   ✓ Items sorted by qty desc: {sorted_check}")
        return success

    def test_risks(self):
        """Test GET /api/risks"""
        success, response = self.run_test(
            "GET /api/risks",
            "GET",
            "risks",
            200,
            check_response=lambda r: 'summary' in r and 'items' in r and len(r['summary']) == 5
        )
        if success:
            print(f"   ✓ Risk buckets: {len(response.get('summary', []))}")
            for bucket in response.get('summary', []):
                print(f"     - {bucket.get('label')}: {bucket.get('count')} SKUs")
            print(f"   ✓ Total items: {len(response.get('items', []))}")
        return success

    def test_forecasting(self):
        """Test GET /api/forecasting"""
        success, response = self.run_test(
            "GET /api/forecasting",
            "GET",
            "forecasting",
            200,
            check_response=lambda r: 'items' in r and all('sparkline' in i and 'confidence' in i for i in r.get('items', []))
        )
        if success:
            print(f"   ✓ Total items: {len(response.get('items', []))}")
            items = response.get('items', [])
            if items:
                first = items[0]
                print(f"   ✓ First item sparkline length: {len(first.get('sparkline', []))} (should be 14)")
                print(f"   ✓ First item confidence: {first.get('confidence')}%")
        
        # Test sort options
        success2, response2 = self.run_test(
            "GET /api/forecasting?sort=confidence_asc",
            "GET",
            "forecasting?sort=confidence_asc",
            200
        )
        
        success3, response3 = self.run_test(
            "GET /api/forecasting?sort=forecast_desc",
            "GET",
            "forecasting?sort=forecast_desc",
            200
        )
        
        return success and success2 and success3

    # ========== PHASE 3 TESTS ==========
    
    def test_shopify_integration_get(self):
        """Test GET /api/integrations/shopify"""
        success, response = self.run_test(
            "GET /api/integrations/shopify",
            "GET",
            "integrations/shopify",
            200,
            check_response=lambda r: 'status' in r and 'data' in r and 'products_imported' in r['data'] and 'sales_records_imported' in r['data']
        )
        if success:
            print(f"   ✓ Status: {response.get('status')}")
            print(f"   ✓ Products imported: {response['data'].get('products_imported')}")
            print(f"   ✓ Sales records imported: {response['data'].get('sales_records_imported')}")
            print(f"   ✓ Events count: {len(response.get('events', []))}")
        return success, response

    def test_shopify_connect(self):
        """Test POST /api/integrations/shopify/connect"""
        success, response = self.run_test(
            "POST /api/integrations/shopify/connect with valid store URL",
            "POST",
            "integrations/shopify/connect",
            200,
            data={"store_url": "ateliersable.myshopify.com"},
            check_response=lambda r: r.get('status') == 'connected' and len(r.get('events', [])) >= 4
        )
        if success:
            print(f"   ✓ Status: {response.get('status')}")
            print(f"   ✓ Store URL: {response.get('store_url')}")
            print(f"   ✓ Events count: {len(response.get('events', []))}")
            print(f"   ✓ Connected at: {response.get('connected_at')}")
        return success

    def test_shopify_connect_invalid(self):
        """Test POST /api/integrations/shopify/connect with invalid URL"""
        success, response = self.run_test(
            "POST /api/integrations/shopify/connect with invalid URL",
            "POST",
            "integrations/shopify/connect",
            400,
            data={"store_url": "invalid"}
        )
        return success

    def test_shopify_sync(self):
        """Test POST /api/integrations/shopify/sync"""
        success, response = self.run_test(
            "POST /api/integrations/shopify/sync",
            "POST",
            "integrations/shopify/sync",
            200,
            check_response=lambda r: r.get('status') == 'connected' and 'last_sync_at' in r
        )
        if success:
            print(f"   ✓ Last sync at: {response.get('last_sync_at')}")
            print(f"   ✓ Events count: {len(response.get('events', []))}")
        return success

    def test_shopify_disconnect(self):
        """Test POST /api/integrations/shopify/disconnect"""
        success, response = self.run_test(
            "POST /api/integrations/shopify/disconnect",
            "POST",
            "integrations/shopify/disconnect",
            200,
            check_response=lambda r: r.get('status') == 'disconnected'
        )
        if success:
            print(f"   ✓ Status: {response.get('status')}")
            print(f"   ✓ Store URL: {response.get('store_url')}")
        return success

    def test_suppliers_list(self):
        """Test GET /api/suppliers"""
        success, response = self.run_test(
            "GET /api/suppliers",
            "GET",
            "suppliers",
            200,
            check_response=lambda r: 'items' in r and len(r['items']) == 6 and all('sku_count' in s and 'inventory_cost' in s and 'categories' in s for s in r['items'])
        )
        if success:
            print(f"   ✓ Total suppliers: {len(response.get('items', []))}")
            for s in response.get('items', [])[:3]:
                print(f"     - {s.get('name')}: {s.get('sku_count')} SKUs, £{s.get('inventory_cost')} inventory, {s.get('lead_time_days')}d lead time")
        return success, response

    def test_supplier_detail(self):
        """Test GET /api/suppliers/{id}"""
        # First get a supplier ID
        success_list, suppliers_response = self.test_suppliers_list()
        if not success_list or not suppliers_response.get('items'):
            return False
        
        supplier_id = suppliers_response['items'][0]['id']
        success, response = self.run_test(
            f"GET /api/suppliers/{supplier_id}",
            "GET",
            f"suppliers/{supplier_id}",
            200,
            check_response=lambda r: 'skus' in r and 'sku_count' in r and 'inventory_cost' in r
        )
        if success:
            print(f"   ✓ Supplier: {response.get('name')}")
            print(f"   ✓ SKU count: {response.get('sku_count')}")
            print(f"   ✓ Inventory cost: £{response.get('inventory_cost')}")
            print(f"   ✓ SKUs list length: {len(response.get('skus', []))}")
        return success

    def test_purchase_orders_list(self):
        """Test GET /api/purchase-orders"""
        success, response = self.run_test(
            "GET /api/purchase-orders",
            "GET",
            "purchase-orders",
            200,
            check_response=lambda r: 'items' in r and 'counts' in r and 'total_open_cost' in r
        )
        if success:
            print(f"   ✓ Total POs: {response.get('total')}")
            print(f"   ✓ Counts by status: {response.get('counts')}")
            print(f"   ✓ Total open cost: £{response.get('total_open_cost')}")
        return success, response

    def test_purchase_order_create(self):
        """Test POST /api/purchase-orders"""
        success, response = self.run_test(
            "POST /api/purchase-orders",
            "POST",
            "purchase-orders",
            200,
            data={
                "lines": [
                    {"sku_id": "SKU-0001", "qty": 50, "unit_cost": 25.00}
                ],
                "notes": "Test PO from API test suite"
            },
            check_response=lambda r: r.get('status') == 'draft' and 'number' in r and 'supplier' in r
        )
        if success:
            print(f"   ✓ PO number: {response.get('number')}")
            print(f"   ✓ Status: {response.get('status')}")
            print(f"   ✓ Total cost: £{response.get('total_cost')}")
            print(f"   ✓ Total units: {response.get('total_units')}")
            print(f"   ✓ Supplier: {response.get('supplier', {}).get('name')}")
        return success, response

    def test_purchase_order_create_no_lines(self):
        """Test POST /api/purchase-orders with no lines (should fail)"""
        success, response = self.run_test(
            "POST /api/purchase-orders with no lines",
            "POST",
            "purchase-orders",
            400,
            data={"lines": []}
        )
        return success

    def test_purchase_order_status_update(self):
        """Test PATCH /api/purchase-orders/{id}/status"""
        # First create a PO
        success_create, po_response = self.test_purchase_order_create()
        if not success_create:
            return False
        
        po_id = po_response.get('id')
        
        # Mark as sent
        success_sent, response_sent = self.run_test(
            f"PATCH /api/purchase-orders/{po_id}/status to 'sent'",
            "PATCH",
            f"purchase-orders/{po_id}/status",
            200,
            data={"status": "sent"},
            check_response=lambda r: r.get('status') == 'sent' and 'sent_at' in r
        )
        if success_sent:
            print(f"   ✓ Status updated to: {response_sent.get('status')}")
            print(f"   ✓ Sent at: {response_sent.get('sent_at')}")
        
        # Mark as received (should increment stock)
        success_received, response_received = self.run_test(
            f"PATCH /api/purchase-orders/{po_id}/status to 'received'",
            "PATCH",
            f"purchase-orders/{po_id}/status",
            200,
            data={"status": "received"},
            check_response=lambda r: r.get('status') == 'received' and 'received_at' in r
        )
        if success_received:
            print(f"   ✓ Status updated to: {response_received.get('status')}")
            print(f"   ✓ Received at: {response_received.get('received_at')}")
        
        return success_sent and success_received

    def test_purchase_order_delete(self):
        """Test DELETE /api/purchase-orders/{id}"""
        # First create a PO
        success_create, po_response = self.test_purchase_order_create()
        if not success_create:
            return False
        
        po_id = po_response.get('id')
        
        success, response = self.run_test(
            f"DELETE /api/purchase-orders/{po_id}",
            "DELETE",
            f"purchase-orders/{po_id}",
            200,
            check_response=lambda r: r.get('deleted') == True
        )
        if success:
            print(f"   ✓ PO deleted successfully")
        return success

    def test_products_pagination(self):
        """Test GET /api/products with pagination"""
        success1, response1 = self.run_test(
            "GET /api/products?page=1&page_size=10",
            "GET",
            "products?page=1&page_size=10",
            200,
            check_response=lambda r: len(r['items']) == 10 and 'page_count' in r
        )
        if success1:
            print(f"   ✓ Page 1 items: {len(response1['items'])}")
            print(f"   ✓ Total: {response1.get('total')}")
            print(f"   ✓ Page count: {response1.get('page_count')}")
        
        success2, response2 = self.run_test(
            "GET /api/products?page=2&page_size=10",
            "GET",
            "products?page=2&page_size=10",
            200,
            check_response=lambda r: len(r['items']) <= 10
        )
        
        return success1 and success2

    def test_products_supplier_filter(self):
        """Test GET /api/products?supplier_id=<id>"""
        # First get a supplier ID
        success_list, suppliers_response = self.test_suppliers_list()
        if not success_list or not suppliers_response.get('items'):
            return False
        
        supplier_id = suppliers_response['items'][0]['id']
        success, response = self.run_test(
            f"GET /api/products?supplier_id={supplier_id}",
            "GET",
            f"products?supplier_id={supplier_id}",
            200,
            check_response=lambda r: all(i.get('supplier_id') == supplier_id for i in r['items']) and all('supplier_name' in i for i in r['items'])
        )
        if success:
            print(f"   ✓ Filtered items: {len(response['items'])}")
            if response['items']:
                print(f"   ✓ Supplier name: {response['items'][0].get('supplier_name')}")
        return success

    def test_recommendations_with_explanation(self):
        """Test GET /api/recommendations with explanation"""
        success, response = self.run_test(
            "GET /api/recommendations (with explanation)",
            "GET",
            "recommendations",
            200,
            check_response=lambda r: 'items' in r and 'by_supplier' in r and all('explanation' in i for i in r['items'])
        )
        if success:
            print(f"   ✓ Items with explanation: {len(response['items'])}")
            print(f"   ✓ By supplier breakdown: {len(response.get('by_supplier', []))} suppliers")
            if response['items']:
                exp = response['items'][0].get('explanation', {})
                print(f"   ✓ Explanation keys: {list(exp.keys())}")
                print(f"   ✓ Drivers count: {len(exp.get('drivers', []))}")
                print(f"   ✓ Math bullets count: {len(exp.get('math', []))}")
        return success

    def test_product_detail_with_explanation(self):
        """Test GET /api/products/{id} with explanation and supplier"""
        success, response = self.run_test(
            "GET /api/products/SKU-0001 (with explanation + supplier)",
            "GET",
            "products/SKU-0001",
            200,
            check_response=lambda r: 'explanation' in r and 'supplier' in r
        )
        if success:
            exp = response.get('explanation', {})
            print(f"   ✓ Explanation headline: {exp.get('headline')}")
            print(f"   ✓ Drivers: {len(exp.get('drivers', []))}")
            print(f"   ✓ Math bullets: {len(exp.get('math', []))}")
            print(f"   ✓ Confidence tier: {exp.get('confidence_tier')}")
            sup = response.get('supplier')
            if sup:
                print(f"   ✓ Supplier: {sup.get('name')}")
        return success

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print(f"📊 TEST SUMMARY")
        print("="*60)
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for i, fail in enumerate(self.failed_tests, 1):
                print(f"\n{i}. {fail['test']}")
                print(f"   Reason: {fail['reason']}")
                if 'detail' in fail:
                    print(f"   Detail: {fail['detail']}")
        
        print("\n" + "="*60)
        return self.tests_passed == self.tests_run

def main():
    print("="*60)
    print("ThreadOS Backend API Test Suite")
    print("="*60)
    print(f"Base URL: https://inventory-intel-14.preview.emergentagent.com/api")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    tester = ThreadOSAPITester()
    
    # Auth tests
    print("\n" + "="*60)
    print("🔐 AUTHENTICATION TESTS")
    print("="*60)
    if not tester.test_login_success():
        print("\n❌ Login failed - cannot proceed with authenticated tests")
        tester.print_summary()
        return 1
    
    tester.test_login_failure()
    tester.test_auth_me()
    
    # Dashboard tests
    print("\n" + "="*60)
    print("📊 DASHBOARD TESTS")
    print("="*60)
    tester.test_dashboard_summary()
    
    # Products tests
    print("\n" + "="*60)
    print("📦 PRODUCTS TESTS")
    print("="*60)
    tester.test_products_list()
    tester.test_products_filters()
    tester.test_product_detail()
    tester.test_sales_history()
    tester.test_forecast()
    
    # Recommendations tests
    print("\n" + "="*60)
    print("💡 RECOMMENDATIONS TESTS")
    print("="*60)
    tester.test_recommendations()
    
    # Risks tests
    print("\n" + "="*60)
    print("⚠️ RISKS TESTS")
    print("="*60)
    tester.test_risks()
    
    # Forecasting tests
    print("\n" + "="*60)
    print("📈 FORECASTING TESTS")
    print("="*60)
    tester.test_forecasting()
    
    # ========== PHASE 3 TESTS ==========
    
    # Shopify integration tests
    print("\n" + "="*60)
    print("🔌 SHOPIFY INTEGRATION TESTS (Phase 3)")
    print("="*60)
    shopify_status, shopify_data = tester.test_shopify_integration_get()
    # If already connected, disconnect first to test connect flow
    if shopify_status and shopify_data.get('status') == 'connected':
        print("\n   ℹ️  Shopify already connected, disconnecting first...")
        tester.test_shopify_disconnect()
    tester.test_shopify_connect()
    tester.test_shopify_connect_invalid()
    tester.test_shopify_sync()
    # Leave connected for frontend tests
    
    # Suppliers tests
    print("\n" + "="*60)
    print("🏭 SUPPLIERS TESTS (Phase 3)")
    print("="*60)
    tester.test_suppliers_list()
    tester.test_supplier_detail()
    
    # Purchase orders tests
    print("\n" + "="*60)
    print("📋 PURCHASE ORDERS TESTS (Phase 3)")
    print("="*60)
    tester.test_purchase_orders_list()
    tester.test_purchase_order_create()
    tester.test_purchase_order_create_no_lines()
    tester.test_purchase_order_status_update()
    tester.test_purchase_order_delete()
    
    # Products pagination & supplier filter tests
    print("\n" + "="*60)
    print("📦 PRODUCTS PAGINATION & SUPPLIER FILTER (Phase 3)")
    print("="*60)
    tester.test_products_pagination()
    tester.test_products_supplier_filter()
    
    # Recommendations with explanation tests
    print("\n" + "="*60)
    print("💡 RECOMMENDATIONS WITH EXPLANATION (Phase 3)")
    print("="*60)
    tester.test_recommendations_with_explanation()
    
    # Product detail with explanation tests
    print("\n" + "="*60)
    print("📦 PRODUCT DETAIL WITH EXPLANATION (Phase 3)")
    print("="*60)
    tester.test_product_detail_with_explanation()
    
    # Print summary
    all_passed = tester.print_summary()
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
