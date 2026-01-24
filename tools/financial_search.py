"""Financial data search tool."""
import os
import json
from typing import Any, Dict, Optional
import httpx


class FinancialSearchTool:
    """Tool for searching financial data."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the financial search tool."""
        self.provider = os.getenv("FINANCIAL_DATA_PROVIDER", "financial_datasets")
        
        if self.provider == "massive":
            self.api_key = os.getenv("MASSIVE_API_KEY")
            self.base_url = "https://api.massive.com"  # Formerly api.polygon.io
        else:
            self.api_key = api_key or os.getenv("FINANCIAL_DATA_PROVIDER_API_KEY") or os.getenv("FINANCIAL_DATASETS_API_KEY")
            self.base_url = "https://api.financialdatasets.ai"
            
        self.client = httpx.Client(timeout=30.0)

    def search(self, query: str, company: Optional[str] = None) -> str:
        """
        Search for financial data.
        
        Args:
            query: Search query (e.g., "revenue", "net income", "cash flow")
            company: Company name or ticker symbol
            
        Returns:
            JSON string with search results
        """
        if self.provider == "massive":
            return json.dumps({"error": "Search tool not implemented for Massive provider yet. Use get_financials."})

        try:
            params = {
                "query": query,
                "api_key": self.api_key,
            }
            if company:
                params["company"] = company

            response = self.client.get(
                f"{self.base_url}/search",
                params=params,
            )
            response.raise_for_status()
            return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

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
            statement_type: Type of statement (income, balance, cash_flow) (also accepts 'statement')
            period: Period type (annual, quarterly)
            
        Returns:
            JSON string with financial data
        """
        # Robust parameter mapping for LLM drift
        ticker = ticker or kwargs.get("company")
        statement_type = statement_type or kwargs.get("statement") or "income"
        
        if not ticker:
            return json.dumps({"error": "Missing 'ticker' or 'company' parameter"})

        try:
            if self.provider == "massive":
                # Massive/Polygon Financials API: /vX/reference/financials
                # Normalizing statement types for Polygon
                # Polygon uses: income_statement, balance_sheet, cash_flow_statement
                ptype = statement_type.lower()
                if "income" in ptype:
                    type_query = "income_statement"
                elif "balance" in ptype:
                    type_query = "balance_sheet"
                elif "cash" in ptype:
                    type_query = "cash_flow_statement"
                else:
                    type_query = ptype

                params = {
                    "ticker": ticker.upper(),
                    "type": type_query,
                    "periodicity": period,
                    "apiKey": self.api_key,
                    "limit": 1
                }
                
                response = self.client.get(
                    f"{self.base_url}/vX/reference/financials",
                    params=params,
                )
            else:
                # Financial Datasets API
                params = {
                    "ticker": ticker,
                    "statement_type": statement_type,
                    "period": period,
                    "api_key": self.api_key,
                }

                response = self.client.get(
                    f"{self.base_url}/financials",
                    params=params,
                )
                
            response.raise_for_status()
            return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    def compare_companies(self, tickers: list[str], metric: str) -> str:
        """
        Compare a metric across multiple companies.
        
        Args:
            tickers: List of stock ticker symbols
            metric: Metric to compare (e.g., "revenue", "net_income")
            
        Returns:
            JSON string with comparison data
        """
        try:
            params = {
                "tickers": ",".join(tickers),
                "metric": metric,
                "api_key": self.api_key,
            }

            response = self.client.get(
                f"{self.base_url}/compare",
                params=params,
            )
            response.raise_for_status()
            return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    def close(self):
        """Close the HTTP client."""
        self.client.close()


class WebSearchTool:
    """Tool for web search using Tavily API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the web search tool."""
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com"
        self.client = httpx.Client(timeout=30.0)

    def search(self, query: str, max_results: int = 5) -> str:
        """
        Search the web for information.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            JSON string with search results
        """
        if not self.api_key:
            return json.dumps({"error": "TAVILY_API_KEY not configured"})

        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
            }

            response = self.client.post(
                f"{self.base_url}/search",
                json=payload,
            )
            response.raise_for_status()
            return json.dumps(response.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    def close(self):
        """Close the HTTP client."""
        self.client.close()
