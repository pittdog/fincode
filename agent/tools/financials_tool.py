import os
import json
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

class FinancialsTool:
    """Tool for retrieving financial statements using Massive (Polygon) or Financial Datasets."""

    def __init__(self):
        self.provider = os.getenv("FINANCIAL_DATA_PROVIDER", "financial_datasets")
        if self.provider == "massive":
            self.api_key = os.getenv("MASSIVE_API_KEY")
            self.base_url = "https://api.massive.com"
        else:
            self.api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
            self.base_url = "https://api.financialdatasets.ai"
        
        self.client = httpx.Client(timeout=30.0)

    def get_financials(
        self,
        ticker: Optional[str] = None,
        statement_type: Optional[str] = None,
        period: str = "annual",
        **kwargs
    ) -> str:
        """
        Get financial statements for a company.
        
        Args:
            ticker: Stock ticker symbol (also accepts 'company')
            statement_type: Type of statement (income, balance, cash_flow)
            period: Period type (annual, quarterly)
        """
        ticker = ticker or kwargs.get("company")
        statement_type = statement_type or kwargs.get("statement") or "income"
        
        if not ticker:
            return json.dumps({"error": "Missing 'ticker' or 'company' parameter"})

        try:
            if self.provider == "massive":
                params = {
                    "ticker": ticker.upper(),
                    "periodicity": period,
                    "apiKey": self.api_key,
                    "limit": 1
                }
                
                response = self.client.get(
                    f"{self.base_url}/vX/reference/financials",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                
                if "results" in data and len(data["results"]) > 0:
                    result = data["results"][0]
                    financials = result.get("financials", {})
                    
                    ptype = statement_type.lower()
                    mkey = None
                    if "income" in ptype:
                        mkey = "income_statement"
                    elif "balance" in ptype:
                        mkey = "balance_sheet"
                    elif "cash" in ptype:
                        mkey = "cash_flow_statement"
                    
                    if mkey and mkey in financials:
                        output = financials[mkey]
                        if isinstance(output, dict):
                            output["_metadata"] = {
                                "ticker": result.get("tickers", [ticker])[0],
                                "fiscal_period": result.get("fiscal_period"),
                                "fiscal_year": result.get("fiscal_year"),
                                "end_date": result.get("end_date")
                            }
                        return json.dumps(output)
                    return json.dumps(financials)
                return json.dumps({"error": f"No financials found for {ticker}"})
            else:
                params = {
                    "ticker": ticker,
                    "statement_type": statement_type,
                    "period": period,
                    "api_key": self.api_key,
                }
                response = self.client.get(f"{self.base_url}/financials", params=params)
                response.raise_for_status()
                return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    def close(self):
        self.client.close()
