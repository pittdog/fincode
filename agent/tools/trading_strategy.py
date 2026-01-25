"""Trading strategy engine for Polymarket weather markets."""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TradeSignal(str, Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    SKIP = "SKIP"


@dataclass
class TradeOpportunity:
    """Represents a trading opportunity."""
    market_id: str
    city: str
    market_question: str
    market_price: float
    fair_price: float
    edge_percentage: float
    signal: TradeSignal
    confidence: float
    liquidity: float
    reasoning: str


class TradingStrategy:
    """Weather-based trading strategy for Polymarket."""

    def __init__(
        self,
        min_liquidity: float = 50.0,
        min_edge: float = 0.15,  # 15% edge minimum
        max_price: float = 0.10,  # 10¢ maximum
        min_confidence: float = 0.60,
    ):
        """Initialize trading strategy.
        
        Args:
            min_liquidity: Minimum liquidity threshold
            min_edge: Minimum edge percentage to trade
            max_price: Maximum price threshold for YES token
            min_confidence: Minimum confidence threshold
        """
        self.min_liquidity = min_liquidity
        self.min_edge = min_edge
        self.max_price = max_price
        self.min_confidence = min_confidence

    def analyze_market(
        self,
        market_id: str,
        city: str,
        market_question: str,
        market_price: float,
        fair_price: float,
        liquidity: float,
    ) -> TradeOpportunity:
        """Analyze a market and generate trading signal.
        
        Args:
            market_id: Market identifier
            city: City name
            market_question: Market question text
            market_price: Current market price (YES token)
            fair_price: Fair price based on weather data
            liquidity: Market liquidity
            
        Returns:
            TradeOpportunity object with signal and analysis
        """
        # Calculate edge
        if market_price <= 0:
            edge_percentage = 0
            confidence = 0
            signal = TradeSignal.SKIP
            reasoning = "Invalid market price"
        else:
            edge_percentage = (fair_price - market_price) / market_price
            
            # Calculate confidence based on multiple factors
            confidence = self._calculate_confidence(
                edge_percentage=edge_percentage,
                market_price=market_price,
                liquidity=liquidity,
                fair_price=fair_price,
            )
            
            # Generate trading signal
            signal = self._generate_signal(
                edge_percentage=edge_percentage,
                market_price=market_price,
                liquidity=liquidity,
                confidence=confidence,
            )
            
            reasoning = self._generate_reasoning(
                signal=signal,
                edge_percentage=edge_percentage,
                market_price=market_price,
                fair_price=fair_price,
                liquidity=liquidity,
                confidence=confidence,
            )

        return TradeOpportunity(
            market_id=market_id,
            city=city,
            market_question=market_question,
            market_price=market_price,
            fair_price=fair_price,
            edge_percentage=edge_percentage,
            signal=signal,
            confidence=confidence,
            liquidity=liquidity,
            reasoning=reasoning,
        )

    def _calculate_confidence(
        self,
        edge_percentage: float,
        market_price: float,
        liquidity: float,
        fair_price: float,
    ) -> float:
        """Calculate confidence score for a trade.
        
        Args:
            edge_percentage: Edge as percentage
            market_price: Current market price
            liquidity: Market liquidity
            fair_price: Fair price
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.5  # Base confidence
        
        # Edge component (higher edge = higher confidence)
        edge_component = min(abs(edge_percentage) / 0.5, 1.0) * 0.3
        confidence += edge_component
        
        # Liquidity component (higher liquidity = higher confidence)
        liquidity_component = min(liquidity / 500.0, 1.0) * 0.2
        confidence += liquidity_component
        
        # Price stability component
        if 0.05 <= market_price <= 0.95:
            confidence += 0.1
        elif 0.01 <= market_price <= 0.99:
            confidence += 0.05
        
        # Fair price reasonableness
        if 0.1 <= fair_price <= 0.9:
            confidence += 0.1
        
        return min(confidence, 1.0)

    def _generate_signal(
        self,
        edge_percentage: float,
        market_price: float,
        liquidity: float,
        confidence: float,
    ) -> TradeSignal:
        """Generate trading signal based on analysis.
        
        Args:
            edge_percentage: Edge as percentage
            market_price: Current market price
            liquidity: Market liquidity
            confidence: Confidence score
            
        Returns:
            TradeSignal enum value
        """
        # Check minimum requirements
        if liquidity < self.min_liquidity:
            return TradeSignal.SKIP
        
        if market_price > self.max_price:
            return TradeSignal.SKIP
        
        if confidence < self.min_confidence:
            return TradeSignal.HOLD
        
        # Positive edge = undervalued = BUY
        if edge_percentage >= self.min_edge:
            return TradeSignal.BUY
        
        # Negative edge = overvalued = SELL
        if edge_percentage <= -self.min_edge:
            return TradeSignal.SELL
        
        return TradeSignal.HOLD

    def _generate_reasoning(
        self,
        signal: TradeSignal,
        edge_percentage: float,
        market_price: float,
        fair_price: float,
        liquidity: float,
        confidence: float,
    ) -> str:
        """Generate human-readable reasoning for the signal.
        
        Args:
            signal: Trading signal
            edge_percentage: Edge as percentage
            market_price: Current market price
            fair_price: Fair price
            liquidity: Market liquidity
            confidence: Confidence score
            
        Returns:
            Reasoning string
        """
        reasoning_parts = []
        
        reasoning_parts.append(f"Signal: {signal.value}")
        reasoning_parts.append(f"Market Price: ${market_price:.4f}")
        reasoning_parts.append(f"Fair Price: ${fair_price:.4f}")
        reasoning_parts.append(f"Edge: {edge_percentage*100:+.2f}%")
        reasoning_parts.append(f"Confidence: {confidence:.2%}")
        reasoning_parts.append(f"Liquidity: ${liquidity:.2f}")
        
        if signal == TradeSignal.BUY:
            reasoning_parts.append(
                f"Market is undervalued by {edge_percentage*100:.2f}%. "
                f"Expected ROI if fair price is reached: {edge_percentage*100:.2f}%"
            )
        elif signal == TradeSignal.SELL:
            reasoning_parts.append(
                f"Market is overvalued by {abs(edge_percentage)*100:.2f}%. "
                f"Expected loss if fair price is reached: {abs(edge_percentage)*100:.2f}%"
            )
        elif signal == TradeSignal.HOLD:
            reasoning_parts.append("Edge is insufficient or confidence is low.")
        else:  # SKIP
            if liquidity < self.min_liquidity:
                reasoning_parts.append(f"Liquidity ${liquidity:.2f} below minimum ${self.min_liquidity:.2f}")
            if market_price > self.max_price:
                reasoning_parts.append(f"Price ${market_price:.4f} above maximum ${self.max_price:.4f}")
        
        return " | ".join(reasoning_parts)

    def rank_opportunities(
        self,
        opportunities: List[TradeOpportunity],
    ) -> List[TradeOpportunity]:
        """Rank opportunities by potential ROI and confidence.
        
        Args:
            opportunities: List of trade opportunities
            
        Returns:
            Sorted list of opportunities
        """
        def score(opp: TradeOpportunity) -> float:
            # Score = edge * confidence * liquidity_factor
            liquidity_factor = min(opp.liquidity / 100.0, 2.0)
            return abs(opp.edge_percentage) * opp.confidence * liquidity_factor

        return sorted(opportunities, key=score, reverse=True)

    def filter_opportunities(
        self,
        opportunities: List[TradeOpportunity],
        signal_type: Optional[TradeSignal] = None,
    ) -> List[TradeOpportunity]:
        """Filter opportunities by signal type.
        
        Args:
            opportunities: List of trade opportunities
            signal_type: Optional signal type to filter by
            
        Returns:
            Filtered list of opportunities
        """
        if signal_type is None:
            return [opp for opp in opportunities if opp.signal != TradeSignal.SKIP]
        
        return [opp for opp in opportunities if opp.signal == signal_type]


class PortfolioSimulator:
    """Simulates portfolio performance."""

    def __init__(self, initial_capital: float = 197.0):
        """Initialize portfolio simulator.
        
        Args:
            initial_capital: Starting capital in dollars
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades: List[Dict[str, Any]] = []
        self.total_roi = 0.0

    def execute_trade(
        self,
        opportunity: TradeOpportunity,
        amount: float,
    ) -> Dict[str, Any]:
        """Simulate executing a trade.
        
        Args:
            opportunity: Trade opportunity
            amount: Amount to invest
            
        Returns:
            Trade execution result
        """
        if self.current_capital < amount:
            return {
                "success": False,
                "reason": "Insufficient capital",
                "capital": self.current_capital,
            }

        # Calculate potential profit/loss
        if opportunity.signal == TradeSignal.BUY:
            # Profit if fair price is reached
            profit = amount * opportunity.edge_percentage
        elif opportunity.signal == TradeSignal.SELL:
            # Profit if price drops
            profit = amount * abs(opportunity.edge_percentage)
        else:
            profit = 0

        # Execute trade
        self.current_capital -= amount
        self.current_capital += amount + profit
        
        roi = profit / amount if amount > 0 else 0
        
        trade = {
            "market_id": opportunity.market_id,
            "city": opportunity.city,
            "signal": opportunity.signal.value,
            "amount": amount,
            "entry_price": opportunity.market_price,
            "fair_price": opportunity.fair_price,
            "profit": profit,
            "roi": roi,
            "confidence": opportunity.confidence,
        }
        
        self.trades.append(trade)
        self.total_roi = (self.current_capital - self.initial_capital) / self.initial_capital
        
        return {
            "success": True,
            "trade": trade,
            "capital": self.current_capital,
            "total_roi": self.total_roi,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get portfolio summary.
        
        Returns:
            Portfolio summary statistics
        """
        total_profit = self.current_capital - self.initial_capital
        
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "total_profit": total_profit,
            "total_roi": self.total_roi,
            "roi_percentage": self.total_roi * 100,
            "num_trades": len(self.trades),
            "winning_trades": len([t for t in self.trades if t["profit"] > 0]),
            "losing_trades": len([t for t in self.trades if t["profit"] < 0]),
        }
