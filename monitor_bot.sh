#!/bin/bash
# Real-time Telegram Bot Monitor
# Usage: ./monitor_bot.sh

echo "======================================"
echo "📊 TELEGRAM BOT LIVE MONITOR"
echo "======================================"
echo "Bot PID: $(pgrep -f telegram_bot.py || echo 'NOT RUNNING')"
echo "Start Time: $(date)"
echo "======================================"
echo ""
echo "Monitoring /tmp/telegram_bot.log..."
echo "Press Ctrl+C to stop"
echo ""
echo "--------------------------------------"

# Follow the log file and highlight important events
tail -f /tmp/telegram_bot.log | while read line; do
    # Color codes
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    PURPLE='\033[0;35m'
    CYAN='\033[0;36m'
    NC='\033[0m' # No Color

    # Detect and highlight different events
    if echo "$line" | grep -q "Signal Detected"; then
        echo -e "${GREEN}🎯 $line${NC}"
    elif echo "$line" | grep -q "Order.*Placed"; then
        echo -e "${BLUE}📝 $line${NC}"
    elif echo "$line" | grep -q "WIN"; then
        echo -e "${GREEN}🏆 $line${NC}"
    elif echo "$line" | grep -q "LOSS"; then
        echo -e "${RED}❌ $line${NC}"
    elif echo "$line" | grep -q "Error\|Failed\|Exception"; then
        echo -e "${RED}⚠️  $line${NC}"
    elif echo "$line" | grep -q "Tracking"; then
        echo -e "${CYAN}🎯 $line${NC}"
    elif echo "$line" | grep -q "Balance"; then
        echo -e "${YELLOW}💰 $line${NC}"
    elif echo "$line" | grep -q "Connecting\|Connected"; then
        echo -e "${PURPLE}🔌 $line${NC}"
    else
        echo "$line"
    fi
done
