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
    
    # Print summary
    all_passed = tester.print_summary()
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
