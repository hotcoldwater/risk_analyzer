export type DartStatusResponse = {
  status: string;
  message?: string;
};

export type CorpSummary = {
  corpCode: string;
  corpName: string;
  stockCode?: string;
  modifyDate?: string;
};

export type CompanyProfile = {
  corpCode: string;
  corpName: string;
  stockCode?: string;
  corpClass?: string;
  industryCode?: string;
  fiscalMonth?: string;
};

export type DartCompanyResponse = DartStatusResponse & {
  corp_code?: string;
  corp_name?: string;
  stock_code?: string;
  corp_cls?: string;
  induty_code?: string;
  est_dt?: string;
  acc_mt?: string;
};

export type DartFinancialStatementItem = {
  rcept_no?: string;
  reprt_code?: string;
  bsns_year?: string;
  corp_code?: string;
  sj_div?: string;
  sj_nm?: string;
  account_id?: string;
  account_nm?: string;
  account_detail?: string;
  thstrm_nm?: string;
  thstrm_amount?: string;
  frmtrm_nm?: string;
  frmtrm_amount?: string;
  bfefrmtrm_nm?: string;
  bfefrmtrm_amount?: string;
  ord?: string;
  currency?: string;
  fs_div?: string;
  fs_nm?: string;
};

export type DartFinancialStatementResponse = DartStatusResponse & {
  list?: DartFinancialStatementItem[];
};
