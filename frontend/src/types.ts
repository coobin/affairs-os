export type User = {
  id: number;
  username: string;
  display_name: string;
  employee_no: string;
  department: number | null;
  department_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  management_scopes: string[];
};

export type AssetRequest = {
  id: number;
  requester: number;
  requester_name: string;
  department_name: string;
  request_type: "assign" | "loan";
  request_type_label: string;
  requested_item_type: "asset" | "inventory";
  requested_item_type_label: string;
  requested_name: string;
  reason: string;
  needed_at: string | null;
  expected_return_at: string | null;
  requested_quantity: number;
  inventory_item: number | null;
  status: "pending" | "fulfilled" | "rejected" | "cancelled";
  status_label: string;
  assigned_asset: number | null;
  assigned_asset_tag: string;
  assigned_asset_name: string;
  issued_inventory_transaction: number | null;
  handled_by_name: string;
  handled_at: string | null;
  manager_notes: string;
  created_at: string;
  updated_at: string;
};

export type DeviceOption = {
  key: string;
  item_type: "asset" | "inventory";
  item_id: number;
  name: string;
  description: string;
  available_count: number;
  unit: string;
};

export type LookupOption = {
  id: number;
  name: string;
  code: string;
  is_active?: boolean;
};

export type InventoryTransaction = {
  id: number;
  action: string;
  action_label: string;
  quantity: number;
  balance_after: number;
  recipient: number | null;
  recipient_name: string;
  actor_name: string;
  notes: string;
  happened_at: string;
};

export type InventoryItem = {
  id: number;
  sku: string;
  name: string;
  kind: string;
  kind_label: string;
  brand: string;
  model_name: string;
  unit: string;
  unit_price: string | null;
  purchase_channel: string;
  purchase_channel_label: string;
  quantity: number;
  minimum_quantity: number;
  location: number | null;
  location_name: string;
  notes: string;
  is_active: boolean;
  low_stock: boolean;
  transactions: InventoryTransaction[];
};

export type StocktakeRecord = {
  id: number;
  asset: number;
  asset_tag: string;
  asset_name: string;
  expected_location_name: string;
  expected_user_name: string;
  result: string;
  result_label: string;
  scanned_at: string | null;
};

export type StocktakeTask = {
  id: number;
  name: string;
  status: string;
  status_label: string;
  scope_location: number | null;
  location_name: string;
  created_by_name: string;
  snapshot_count: number;
  scanned_count: number;
  missing_count: number;
  created_at: string;
  completed_at: string | null;
  records: StocktakeRecord[];
};

export type Reports = {
  summary: { assets: number; purchase_cost: string; in_use: number; available: number };
  by_category: { category__name: string | null; total: number }[];
  by_department: { custodian_department_id: number | null; custodian_department__name: string | null; total: number }[];
  by_status: { status: string; label: string; total: number }[];
  quality: {
    missing_category: number;
    missing_location: number;
    missing_serial: number;
    import_warnings: number;
  };
  low_stock: InventoryItem[];
};

export type StatusOption = {
  value: string;
  label: string;
};

export type Lookups = {
  users: User[];
  departments: LookupOption[];
  locations: (LookupOption & { kind: string; kind_label: string; address: string })[];
  categories: (LookupOption & { class_type: "IT" | "ADMIN"; class_type_label: string; icon: string; description: string; custom_fields: unknown[] })[];
  statuses: StatusOption[];
};

export type AssetEvent = {
  id: number;
  action: string;
  action_label: string;
  from_status: string;
  to_status: string;
  actor_name: string;
  from_user_name: string;
  to_user_name: string;
  from_location_name: string;
  to_location_name: string;
  happened_at: string;
  notes: string;
};

export type Asset = {
  id: number;
  asset_tag: string;
  kingdee_code: string;
  name: string;
  category: number;
  category_name: string;
  category_code: string;
  category_class_type: "IT" | "ADMIN";
  category_class_type_label: string;
  brand: string;
  model_name: string;
  serial_number: string;
  specification: string;
  cpu: string;
  memory: string;
  storage: string;
  wired_mac: string;
  wireless_mac: string;
  status: string;
  status_label: string;
  current_location: number | null;
  location_name: string;
  assigned_to: number | null;
  assignee_name: string;
  custodian_department: number | null;
  department_name: string;
  purchase_date: string | null;
  purchase_cost: string | null;
  warranty_expires_at: string | null;
  expected_return_at: string | null;
  notes: string;
  custom_data: Record<string, unknown>;
  last_audited_at: string | null;
  created_at: string;
  updated_at: string;
  events: AssetEvent[];
  is_warranty_due: boolean;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type AssetImportRow = {
  row_number: number;
  action: "create" | "update";
  errors: string[];
  warnings: string[];
  asset_tag: string;
  name: string;
  category: string;
  class_type: string;
  brand_model: string;
  assignee: string;
  status: string;
};

export type AssetImportPreview = {
  total: number;
  create: number;
  update: number;
  invalid: number;
  warning: number;
  rows: AssetImportRow[];
  truncated: boolean;
};

export type Dashboard = {
  summary: {
    total: number;
    available: number;
    assigned: number;
    attention: number;
  };
  tasks: {
    warranty_due: number;
    overdue_loans: number;
    attention: number;
  };
  admin_tasks: {
    pending_vehicle_dispatches: number;
    due_vehicle_documents: number;
    pending_purchase_requests: number;
    expiring_contracts: number;
  };
  status_distribution: {
    status: string;
    label: string;
    total: number;
  }[];
  recent_events: AssetEvent[];
  generated_at: string;
};

export type ExpenseCategory = { id: number; name: string; code: string; budget_code: string; is_active: boolean };
export type Supplier = { id: number; code: string; name: string; channel: string; channel_label: string; contact_name: string; contact_phone: string; contact_email: string; tax_number: string; bank_account: string; address: string; notes: string; is_active: boolean };
export type Vehicle = { id: number; plate_number: string; name: string; brand: string; model_name: string; vin: string; engine_number: string; energy_type: string; energy_type_label: string; seats: number; status: string; status_label: string; department: number | null; department_name: string; custodian: number | null; custodian_name: string; purchase_date: string | null; purchase_cost: string | null; current_mileage: number; insurance_expires_at: string | null; inspection_expires_at: string | null; notes: string };
export type VehicleDispatch = { id: number; request_no: string; requester: number; requester_name: string; department_name: string; purpose: string; destination: string; passenger_count: number; planned_departure_at: string; planned_return_at: string; vehicle: number | null; vehicle_label: string; driver: number | null; driver_name: string; driver_display: string; status: string; status_label: string; start_mileage: number | null; end_mileage: number | null; actual_departure_at: string | null; actual_return_at: string | null; handled_by_name: string; notes: string; created_at: string };
export type VehicleExpense = { id: number; vehicle: number; vehicle_label: string; expense_type: string; expense_type_label: string; occurred_on: string; amount: string; supplier: number | null; supplier_name: string; odometer: number | null; next_due_on: string | null; next_due_mileage: number | null; notes: string; created_at: string };
export type AdministrativeExpense = { id: number; occurred_on: string; fiscal_year: number; category: number; category_name: string; department: number | null; department_name: string; supplier: number | null; supplier_name: string; contract: number | null; contract_name: string; amount_type: string; amount_type_label: string; amount: string; title: string; source_type: string; source_no: string; object_label: string; invoice_status: string; invoice_status_label: string; invoice_number: string; kingdee_code: string; external_id: string; sync_status: string; notes: string; created_by_name: string };
export type ExpenseSummary = { year: number; totals: { estimated: string; approved: string; committed: string; actual: string; reversal: string; net_actual: string }; by_category: { category__name: string; total: string }[]; by_month: { month: number; total: string }[] };
export type Contract = { id: number; contract_no: string; name: string; supplier: number | null; supplier_name: string; category: number | null; category_name: string; department: number | null; department_name: string; owner: number | null; owner_name: string; status: string; status_label: string; start_date: string | null; end_date: string | null; amount: string; renewal_notice_days: number; auto_renew: boolean; kingdee_code: string; external_id: string; notes: string; days_to_expiry: number | null };
export type PurchaseLine = { id?: number; name: string; specification: string; quantity: string | number; unit: string; estimated_unit_price?: string | number; unit_price?: string | number; line_amount?: string };
export type PurchaseRequest = { id: number; request_no: string; requester: number; requester_name: string; department_name: string; needed_on: string | null; reason: string; status: string; status_label: string; estimated_amount: string; category: number | null; category_name: string; handled_by_name: string; manager_notes: string; items: PurchaseLine[]; created_at: string };
export type PurchaseOrder = { id: number; order_no: string; request: number | null; request_no: string; supplier: number; supplier_name: string; contract: number | null; contract_name: string; status: string; status_label: string; ordered_on: string | null; expected_on: string | null; received_on: string | null; total_amount: string; kingdee_code: string; external_id: string; notes: string; items: PurchaseLine[]; created_by_name: string };
