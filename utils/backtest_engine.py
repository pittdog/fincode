"""Backtest engine for Polymarket weather strategy."""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import re

from agent.tools.polymarket_tool import PolymarketClient
from agent.tools.visual_crossing_client import VisualCrossingClient
from agent.tools.trading_strategy import TradingStrategy, TradeSignal

logger = logging.getLogger(__name__)

class BacktestEngine:
    """Engine for running historical simulations of the weather strategy."""

    def __init__(
        self,
        polymarket_client: PolymarketClient,
        weather_client: VisualCrossingClient,
        strategy_params: Optional[Dict[str, Any]] = None
    ):
        """Initialize the backtest engine.
        
        Args:
            polymarket_client: Client for Polymarket data
            weather_client: Client for Visual Crossing data
            strategy_params: Optional overrides for TradingStrategy
        """
        self.pm_client = polymarket_client
        self.vc_client = weather_client
        self.strategy = TradingStrategy(**(strategy_params or {}))

    async def run_backtest(
        self,
        city: str,
        target_date: str,
        market_id: Optional[str] = None,
        lookback_days: int = 7
    ) -> Dict[str, Any]:
        """Run a backtest for a specific city and date.
        
        Args:
            city: City name
            target_date: Target resolution date (YYYY-MM-DD)
            market_id: Optional market ID override
            lookback_days: Number of days to look back from target_date
            
        Returns:
            Backtest results summary
        """
        # 1. Discover market if not provided
        gamma_id = market_id
        clob_id = None
        
        if not gamma_id:
            logger.info(f"Searching for market ID for {city} on {target_date}...")
            gamma_id = await self.pm_client.find_market_id(city, target_date)
            if not gamma_id:
                return {"success": False, "error": f"Could not find market for {city} {target_date}"}

        # 2. Fetch Market Details using Gamma ID
        market = await self.pm_client.get_market_by_id(gamma_id)
        if not market:
            return {"success": False, "error": f"Market metadata not found for {gamma_id}"}
        
        clob_id = market.clob_token_ids[0] if market.clob_token_ids else gamma_id

        # 3. Fetch Price History
        logger.info(f"Fetching price history for {clob_id}...")
        price_history = await self.pm_client.get_price_history(clob_id)
        if not price_history:
             return {"success": False, "error": f"No price history found for {market_id}"}

        # 4. Fetch Weather Observations (Ground Truth)
        logger.info(f"Fetching weather for {city} on {target_date}...")
        actual_weather = await self.vc_client.get_day_weather(city, target_date)
        if not actual_weather:
            return {"success": False, "error": f"Could not fetch weather data for {city} {target_date}"}

        # 5. Simulation based on checkpoints
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        checkpoints = ["09:00", "14:00", "20:00"]
        
        # Fetch weather for the range
        weather_range = await self.vc_client.get_historical_weather_range(city, target_date, days=lookback_days)
        weather_map = {d["datetime"]: d for d in weather_range}
        
        simulation_steps = []
        virtual_trades = []
        resolution = self._determine_resolution(actual_weather, market.question)
        threshold_info = self._parse_threshold(market.question)
        fair_probabilities = self._calculate_probabilities(actual_weather, market.question)
        fair_price = fair_probabilities.get("probability", 0.5)

        for offset in range(lookback_days, -1, -1):
            current_day_dt = target_dt - timedelta(days=offset)
            day_str = current_day_dt.strftime("%Y-%m-%d")
            day_weather = weather_map.get(day_str, {})
            
            for cp_time in checkpoints:
                check_dt = datetime.strptime(f"{day_str} {cp_time}", "%Y-%m-%d %H:%M")
                checkpoint_unix = check_dt.timestamp()
                
                # Find hourly weather for this checkpoint
                hourly_weather = {}
                found_hour = False
                for hour in day_weather.get("hours", []):
                    # hour["datetime"] is HH:MM:SS
                    if hour["datetime"].startswith(cp_time):
                        hourly_weather = hour
                        found_hour = True
                        break
                
                if not found_hour:
                    logger.debug(f"No hourly weather found for {day_str} {cp_time}")

                # Find the closest price point to this checkpoint
                closest_price = 0.5
                min_diff = 3600
                for point in price_history:
                    pt_ts = point.get("t", 0)
                    diff = abs(pt_ts - checkpoint_unix)
                    if diff < min_diff:
                        min_diff = diff
                        closest_price = point.get("y", point.get("price", 0.5))

                opp = self.strategy.analyze_market(
                    market_id=gamma_id,
                    city=city,
                    market_question=market.question,
                    market_price=closest_price,
                    fair_price=fair_price,
                    liquidity=market.liquidity
                )

                if opp.signal == TradeSignal.BUY:
                    virtual_trades.append({
                        "timestamp": check_dt.isoformat(),
                        "price": closest_price,
                        "edge": opp.edge_percentage,
                        "confidence": opp.confidence
                    })
                
                simulation_steps.append({
                    "time": check_dt.isoformat(),
                    "day_offset": -offset,
                    "market_price": closest_price,
                    "fair_price": fair_price,
                    "edge": opp.edge_percentage,
                    "signal": opp.signal.value,
                    "actual_temp_checkpoint": hourly_weather.get("temp", "N/A"),
                    "actual_day_max_temp": actual_weather.get("tempmax"),
                    "forecast_day_max_temp": day_weather.get("tempmax") if offset > 0 else "N/A", # Simulating forecast 
                    "target_threshold_f": threshold_info.get("value"),
                    "original_threshold_c": threshold_info.get("original"),
                    "target_resolution": resolution
                })

        summary = {
            "success": True,
            "city": city,
            "target_date": target_date,
            "market_id": gamma_id,
            "question": market.question,
            "weather": actual_weather,
            "resolution": resolution,
            "num_price_points": len(simulation_steps),
            "num_buy_signals": len([s for s in simulation_steps if s["signal"] == "BUY"]),
            "trades": virtual_trades,
            "pnl": self._calculate_pnl(virtual_trades, resolution),
            "simulation": simulation_steps
        }
        
        return summary

    def _parse_threshold(self, question: str) -> Dict[str, Any]:
        """Extract temperature threshold and unit from question.
        
        Example: "Will temp in Seoul be -2°C or below?" -> {'value': 28.4, 'unit': 'F', 'original': -2.0}
        """
        # Match "number°C" or "number°F" or just "number" (fallback)
        # Handles negative numbers too
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*°?([CF])", question, re.IGNORECASE)
        if not match:
             # Fallback: just look for a number
             match = re.search(r"(-?\d+(?:\.\d+)?)", question)
             if not match:
                 return {"value": 0.0, "unit": "F"}
             return {"value": float(match.group(1)), "unit": "F"}
        
        val = float(match.group(1))
        unit = match.group(2).upper()
        
        if unit == 'C':
            # Convert to Fahrenheit
            f_val = (val * 9/5) + 32
            return {"value": f_val, "unit": "F", "original": val, "original_unit": "C"}
        
        return {"value": val, "unit": "F"}

    def _calculate_probabilities(self, weather: Dict[str, Any], question: str) -> Dict[str, float]:
        """Heuristic for fair price based on observed weather."""
        threshold_info = self._parse_threshold(question)
        target_val = threshold_info["value"] # F
        actual_val = weather.get("tempmax", 0) # F
        
        diff = actual_val - target_val
        
        is_above = "or higher" in question.lower() or "exceed" in question.lower() or "above" in question.lower()
        is_below = "or below" in question.lower() or "below" in question.lower() or "less than" in question.lower()
        is_discrete = not (is_above or is_below)

        if is_discrete:
            # Probability is high if actual matches the specific bucket (within 1 degree F)
            abs_diff = abs(diff)
            if abs_diff < 1.0: prob = 0.95
            elif abs_diff < 2.0: prob = 0.70
            elif abs_diff < 3.0: prob = 0.30
            else: prob = 0.05
        elif is_below:
            if diff < -2.0: prob = 0.95
            elif diff > 2.0: prob = 0.05
            else: prob = 0.5 - (diff / 4.0)
        else: # is_above
            if diff > 2.0: prob = 0.95
            elif diff < -2.0: prob = 0.05
            else: prob = 0.5 + (diff / 4.0)

        return {"probability": prob, "threshold_f": target_val, "actual_f": actual_val}

    def _determine_resolution(self, weather: Dict[str, Any], question: str) -> float:
        """Determine if the YES token resolved to 1.0 or 0.0."""
        threshold_info = self._parse_threshold(question)
        target_f = threshold_info["value"]
        actual_f = weather.get("tempmax", 0)
        
        is_above = "or higher" in question.lower() or "exceed" in question.lower() or "above" in question.lower()
        is_below = "or below" in question.lower() or "below" in question.lower() or "less than" in question.lower()
        is_discrete = not (is_above or is_below)
        
        if is_discrete:
            # Resolution for a specific bucket (e.g. "be -3°C")
            # Using 1 degree F tolerance for integer bucket match
            return 1.0 if abs(actual_f - target_f) < 1.0 else 0.0
        elif is_below:
            return 1.0 if actual_f <= target_f else 0.0
        else: # is_above
            return 1.0 if actual_f >= target_f else 0.0

    def _calculate_pnl(self, trades: List[Dict[str, Any]], resolution: float) -> Optional[Dict[str, Any]]:
        if not trades:
            return None
            
        total_spent = sum(t["price"] for t in trades)
        total_payout = len(trades) * resolution
        profit = total_payout - total_spent
        roi = (profit / total_spent) if total_spent > 0 else 0
        
        return {
            "total_invested": total_spent,
            "total_payout": total_payout,
            "profit": profit,
            "roi": roi
        }
