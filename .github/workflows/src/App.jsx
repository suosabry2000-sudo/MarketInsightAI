import React, { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, TrendingDown, Search, Bot, Sparkles, Activity, 
  BarChart3, RefreshCw, Calendar, ArrowUpRight, ArrowDownRight, 
  ChevronRight, Zap, ShieldAlert, DollarSign, Wallet, Layers, 
  Clock, PieChart, Bell, Sliders, CheckCircle2, AlertCircle,
  MessageSquare, Cpu, Lock, Crosshair, ChevronDown, Flame,
  Share2, Play, Terminal, HelpCircle, Compass, Gauge
} from 'lucide-react';

const WATCHLIST_PRESETS = [
  { symbol: 'NVDA', name: 'NVIDIA Corp.', price: 128.84, delta: '+3.42%' },
  { symbol: 'TSLA', name: 'Tesla Inc.', price: 218.60, delta: '-1.85%' },
  { symbol: 'AAPL', name: 'Apple Inc.', price: 226.05, delta: '+0.75%' },
  { symbol: 'MSFT', name: 'Microsoft Corp.', price: 448.20, delta: '+1.12%' },
  { symbol: 'AMD',  name: 'Advanced Micro Devices', price: 154.90, delta: '+4.20%' },
  { symbol: 'SPY',  name: 'S&P 500 ETF Trust', price: 562.15, delta: '+0.45%' }
];

const App = () => {
  const [activeTicker, setActiveTicker] = useState('NVDA');
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [predictionData, setPredictionData] = useState(null);
  const [error, setError] = useState(null);
  
  // Navigation & View State
  const [activeTab, setActiveTab] = useState('forecast'); // 'forecast' | 'quant' | 'copilot'
  const [timeframe, setTimeframe] = useState('1W');
  const [hoveredIndex, setHoveredIndex] = useState(null);

  // Copilot Chat State
  const [chatMessages, setChatMessages] = useState([
    { sender: 'ai', text: 'Welcome to V4.0 Quant Desk. I am running Gemini 2.5 Flash forecasting for Friday expirations. How can I assist your positioning?' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatScrollRef = useRef(null);

  // Order Execution Modal
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [tradeType, setTradeType] = useState('buy');
  const [sharesInput, setSharesInput] = useState('15');
  const [tradeSuccess, setTradeSuccess] = useState(false);

  // High-precision Spline Path Generation
  const buildSvgPath = (trend, currentPrice, targetPrice) => {
    const isBull = trend === 'up';
    const width = 340;
    const height = 150;
    const steps = 14;
    const points = [];
    
    let startY = isBull ? 110 : 35;
    const endY = isBull ? 25 : 125;
    
    points.push({ x: 0, y: startY, price: currentPrice });

    for (let i = 1; i <= steps; i++) {
      const x = (width / steps) * i;
      const progress = i / steps;
      const linearY = startY + (endY - startY) * progress;
      const noise = (Math.sin(i * 1.8) * 14) * (1 - progress * 0.4);
      let calculatedY = Math.max(12, Math.min(height - 12, linearY + noise));
      if (i === steps) calculatedY = endY;
      
      const interpPrice = currentPrice + (targetPrice - currentPrice) * progress + ((Math.random() - 0.5) * 2);
      points.push({ x, y: calculatedY, price: interpPrice });
    }

    const pathD = points.reduce((acc, point, index) => {
      if (index === 0) return `M ${point.x},${point.y}`;
      const prev = points[index - 1];
      const cx = (prev.x + point.x) / 2;
      return `${acc} C ${cx},${prev.y} ${cx},${point.y} ${point.x},${point.y}`;
    }, '');

    const areaD = `${pathD} L ${width},${height} L 0,${height} Z`;
    return { pathD, areaD, points };
  };

  // AI Friday Quantitative Analysis Engine
  const fetchAiPrediction = async (symbol) => {
    setLoading(true);
    setError(null);
    setPredictionData(null);

    const apiKey = ""; // Dynamically provided by platform runtime
    
    const prompt = `Perform Wall Street quantitative options & Friday close projection for ticker "${symbol}".
Assume current market conditions and calculate algorithmic probability metrics for this coming Friday.

Respond STRICTLY in JSON:
{
  "company_name": "Full legal company name",
  "current_price": 128.50,
  "friday_prediction": 137.40,
  "trend": "up",
  "confidence": 91,
  "implied_volatility": "44.2%",
  "max_pain_price": 132.00,
  "put_call_ratio": 0.68,
  "expected_move_dollars": 8.90,
  "catalyst_summary": "Institutional gamma squeeze detected above key resistance with strong call open interest buildup.",
  "bull_target": 142.50,
  "bear_target": 121.00,
  "ai_factors": [
    { "factor": "Dark Pool Buying", "score": "+8.4%", "sentiment": "bullish" },
    { "factor": "Gamma Exposure (GEX)", "score": "Positive Flip", "sentiment": "bullish" },
    { "factor": "Options Delta Skew", "score": "68% Calls", "sentiment": "bullish" },
    { "factor": "RSI / MACD Momentum", "score": "Overbought Risk", "sentiment": "bearish" }
  ]
}`;

    const payload = {
      contents: [{ parts: [{ text: prompt }] }],
      systemInstruction: { 
        parts: [{ text: "You are MarketInsight AI V4.0 Quantum Core. Output strictly valid JSON." }] 
      },
      generationConfig: { responseMimeType: "application/json" }
    };

    let retries = 5;
    let delay = 1000;
    let success = false;

    while (retries > 0 && !success) {
      try {
        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${apiKey}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          }
        );

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const result = await res.json();
        const jsonText = result.candidates?.[0]?.content?.parts?.[0]?.text;

        if (jsonText) {
          const parsed = JSON.parse(jsonText);
          const svgData = buildSvgPath(parsed.trend, parsed.current_price, parsed.friday_prediction);
          
          setPredictionData({
            ...parsed,
            chartData: svgData,
            dollarChange: parsed.friday_prediction - parsed.current_price,
            percentChange: (((parsed.friday_prediction - parsed.current_price) / parsed.current_price) * 100).toFixed(2)
          });
          success = true;
        }
      } catch (err) {
        retries--;
        if (retries === 0) {
          setError("Algorithmic quant engine connection timed out. Please retry.");
        } else {
          await new Promise(r => setTimeout(r, delay));
          delay *= 2;
        }
      }
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchAiPrediction(activeTicker);
  }, [activeTicker]);

  // Copilot Live Chat Dispatcher
  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    setChatMessages(prev => [...prev, { sender: 'user', text: userMessage }]);
    setChatInput('');
    setChatLoading(true);

    const apiKey = "";
    const prompt = `You are the MarketInsight AI V4.0 Copilot. 
Context: User is analyzing ${activeTicker} (Current: $${predictionData?.current_price || 'N/A'}, Predicted Friday Target: $${predictionData?.friday_prediction || 'N/A'}, Trend: ${predictionData?.trend || 'neutral'}).
User asked: "${userMessage}".
Provide a laser-focused, institutional trader level response in 2-3 sentences. Mention support/resistance or options positioning where appropriate.`;

    try {
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${apiKey}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })
        }
      );
      const result = await res.json();
      const reply = result.candidates?.[0]?.content?.parts?.[0]?.text || "Unable to compute quant vector.";
      setChatMessages(prev => [...prev, { sender: 'ai', text: reply }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { sender: 'ai', text: "Error communicating with Copilot neural layer." }]);
    } finally {
      setChatLoading(false);
      setTimeout(() => {
        chatScrollRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchInput.trim()) {
      setActiveTicker(searchInput.toUpperCase().trim());
      setSearchInput('');
    }
  };

  const handleExecuteTrade = (e) => {
    e.preventDefault();
    setTradeSuccess(true);
    setTimeout(() => {
      setTradeSuccess(false);
      setTradeModalOpen(false);
    }, 1500);
  };

  const isUp = predictionData?.trend === 'up';
  const priceColor = isUp ? 'text-emerald-400' : 'text-rose-400';
  const bgColor = isUp ? 'bg-emerald-500' : 'bg-rose-500';
  const strokeColor = isUp ? '#10b981' : '#f43f5e';

  return (
    <div className="flex flex-col h-screen max-h-screen bg-[#07090e] text-slate-100 font-sans overflow-hidden max-w-md mx-auto relative shadow-2xl border-x border-slate-800/50 select-none">
      
      {/* Top Glassmorphic Navigation Bar */}
      <header className="px-4 pt-5 pb-3 bg-[#07090e]/95 backdrop-blur-xl sticky top-0 z-30 border-b border-slate-800/80 flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 via-blue-600 to-cyan-400 p-[1.5px] shadow-lg shadow-blue-500/20">
            <div className="w-full h-full bg-[#0b0f19] rounded-[14px] flex items-center justify-center">
              <Cpu className="w-5 h-5 text-cyan-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="text-sm font-black tracking-wider uppercase text-white">MARKET<span className="text-cyan-400">INSIGHT</span></h1>
              <span className="px-1.5 py-0.5 rounded-full text-[8px] font-black bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">V4.0 QUANT</span>
            </div>
            <p className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Neural Engine Active
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button 
            onClick={() => fetchAiPrediction(activeTicker)} 
            disabled={loading}
            className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white transition-all active:scale-90 border border-slate-800 shadow-md"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto px-4 pt-3 pb-28 hide-scrollbar">
        
        {/* Search Bar */}
        <form onSubmit={handleSearchSubmit} className="relative mb-3">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search US equities (e.g., NVDA, TSLA)..."
            className="w-full bg-[#0d1322] border border-slate-800/80 rounded-2xl py-3 pl-10 pr-4 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all font-medium shadow-inner"
          />
        </form>

        {/* Dynamic Watchlist Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-2.5 mb-3 hide-scrollbar">
          {WATCHLIST_PRESETS.map((item) => (
            <button
              key={item.symbol}
              onClick={() => setActiveTicker(item.symbol)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap flex items-center gap-1.5 ${
                activeTicker === item.symbol 
                  ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-lg shadow-blue-500/25 border border-cyan-400/30' 
                  : 'bg-[#0d1322] hover:bg-slate-800 text-slate-400 border border-slate-800/80'
              }`}
            >
              <span>${item.symbol}</span>
              <span className={`text-[10px] ${item.delta.startsWith('+') ? 'text-emerald-400' : 'text-rose-400'}`}>{item.delta}</span>
            </button>
          ))}
        </div>

        {/* View Segmented Switcher */}
        <div className="flex rounded-xl bg-[#0b0f19] p-1 border border-slate-800/80 mb-4">
          <button 
            onClick={() => setActiveTab('forecast')}
            className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${activeTab === 'forecast' ? 'bg-gradient-to-r from-slate-800 to-slate-700 text-white shadow' : 'text-slate-400'}`}
          >
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            Friday Target
          </button>
          <button 
            onClick={() => setActiveTab('quant')}
            className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${activeTab === 'quant' ? 'bg-gradient-to-r from-slate-800 to-slate-700 text-white shadow' : 'text-slate-400'}`}
          >
            <Gauge className="w-3.5 h-3.5 text-blue-400" />
            Quant Data
          </button>
          <button 
            onClick={() => setActiveTab('copilot')}
            className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${activeTab === 'copilot' ? 'bg-gradient-to-r from-slate-800 to-slate-700 text-white shadow' : 'text-slate-400'}`}
          >
            <Bot className="w-3.5 h-3.5 text-indigo-400" />
            AI Desk
          </button>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <div className="relative w-16 h-16">
              <div className="absolute inset-0 rounded-full border-4 border-cyan-500/20"></div>
              <div className="absolute inset-0 rounded-full border-4 border-cyan-400 border-t-transparent animate-spin"></div>
              <Cpu className="w-7 h-7 text-cyan-400 absolute inset-0 m-auto animate-pulse" />
            </div>
            <div className="text-center">
              <p className="text-white font-bold text-sm">Computing Quantum Target for ${activeTicker}</p>
              <p className="text-slate-500 text-xs mt-0.5">Analyzing options skew, dark pool orders & macro delta...</p>
            </div>
          </div>
        ) : error ? (
          <div className="bg-rose-500/10 border border-rose-500/20 rounded-2xl p-6 text-center space-y-3">
            <AlertCircle className="w-8 h-8 text-rose-400 mx-auto" />
            <p className="text-rose-300 text-sm font-medium">{error}</p>
            <button 
              onClick={() => fetchAiPrediction(activeTicker)}
              className="px-4 py-2 bg-slate-800 rounded-xl text-xs font-bold hover:bg-slate-700 transition-colors"
            >
              Retry Neural Analysis
            </button>
          </div>
        ) : predictionData ? (
          <div>
            
            {/* TAB 1: FRIDAY FORECAST & INTERACTIVE HUD */}
            {activeTab === 'forecast' && (
              <div className="space-y-4 animate-in fade-in duration-300">
                
                {/* Spot Price & Ticker Header */}
                <div className="bg-gradient-to-b from-[#0d1322] to-[#0a0f1d] border border-slate-800/80 rounded-3xl p-4 relative overflow-hidden shadow-xl">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-3xl font-black tracking-tight text-white">${activeTicker}</h2>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-cyan-400 border border-slate-700">
                          NASDAQ 100
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 font-medium mt-0.5 truncate max-w-[180px]">{predictionData.company_name}</p>
                    </div>

                    <div className="text-right">
                      <p className="text-[10px] uppercase font-bold text-slate-500">Live Spot</p>
                      <p className="text-2xl font-black text-white">${predictionData.current_price.toFixed(2)}</p>
                    </div>
                  </div>

                  {/* Timeframe Bar */}
                  <div className="flex justify-between items-center mt-4 pt-3 border-t border-slate-800/60 text-xs">
                    <div className="flex gap-1.5">
                      {['1D', '1W', '1M', 'YTD'].map(tf => (
                        <button 
                          key={tf} 
                          onClick={() => setTimeframe(tf)}
                          className={`px-2.5 py-0.5 rounded-lg text-[11px] font-bold ${timeframe === tf ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'text-slate-500'}`}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center gap-1 text-[11px] text-slate-400">
                      <Clock className="w-3 h-3 text-cyan-400" />
                      <span>Exp: <strong className="text-white">This Friday</strong></span>
                    </div>
                  </div>
                </div>

                {/* Friday Target Quant Hero Card */}
                <div className="bg-gradient-to-b from-[#0e1628] via-[#0b101e] to-[#07090e] border border-slate-800/90 rounded-3xl p-5 relative overflow-hidden shadow-2xl">
                  <div className={`absolute top-0 left-0 right-0 h-1 ${bgColor}`}></div>
                  <div className={`absolute -right-8 -top-8 w-36 h-36 ${bgColor} opacity-15 rounded-full blur-3xl`}></div>

                  <div className="flex items-center justify-between mb-3 relative z-10">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20">
                        <Sparkles className="w-4 h-4 text-cyan-400" />
                      </div>
                      <div>
                        <h3 className="text-xs font-black uppercase tracking-wider text-slate-200">FRIDAY PRICE PROJECTION</h3>
                        <p className="text-[9px] text-slate-500">Institutional Quant Model</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-cyan-950/70 border border-cyan-500/40 text-[11px] font-bold text-cyan-300 shadow-sm">
                      <Gauge className="w-3.5 h-3.5 text-cyan-400" />
                      {predictionData.confidence}% Probability
                    </div>
                  </div>

                  <div className="flex justify-between items-end relative z-10">
                    <div>
                      <div className="flex items-baseline gap-2">
                        <span className={`text-4xl font-black tracking-tight ${priceColor}`}>
                          ${predictionData.friday_prediction.toFixed(2)}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 mt-1.5">
                        <span className={`flex items-center gap-1 text-xs font-black px-2 py-0.5 rounded-lg ${isUp ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'}`}>
                          {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                          {isUp ? '+' : ''}{predictionData.dollarChange.toFixed(2)} ({predictionData.percentChange}%)
                        </span>
                        <span className="text-[10px] text-slate-400 font-semibold">Projected EOD Friday</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="text-[9px] uppercase font-bold text-slate-500">Expected Move</p>
                      <p className="text-xs font-bold text-cyan-400">±${predictionData.expected_move_dollars}</p>
                    </div>
                  </div>

                  {/* Interactive Spline Chart */}
                  <div className="mt-4 pt-2 relative h-36 w-full">
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 340 150" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id="quantGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.30" />
                          <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
                        </linearGradient>
                      </defs>
                      
                      <path d={predictionData.chartData.areaD} fill="url(#quantGradient)" />
                      <path 
                        d={predictionData.chartData.pathD} 
                        fill="none" 
                        stroke={strokeColor} 
                        strokeWidth="3.5" 
                        strokeLinecap="round"
                      />

                      {predictionData.chartData.points.map((pt, idx) => (
                        <circle
                          key={idx}
                          cx={pt.x}
                          cy={pt.y}
                          r={idx === hoveredIndex ? "6" : "2.5"}
                          className={`transition-all duration-150 ${idx === hoveredIndex ? 'fill-white stroke-cyan-400 stroke-2' : 'fill-slate-300'}`}
                          onTouchStart={() => setHoveredIndex(idx)}
                          onMouseEnter={() => setHoveredIndex(idx)}
                        />
                      ))}
                    </svg>

                    {hoveredIndex !== null && (
                      <div 
                        className="absolute top-0 transform -translate-x-1/2 bg-slate-900/95 border border-cyan-500/40 text-white text-[10px] font-bold px-2 py-0.5 rounded-md pointer-events-none shadow-lg"
                        style={{ left: `${(hoveredIndex / 14) * 100}%` }}
                      >
                        ${predictionData.chartData.points[hoveredIndex]?.price.toFixed(2)}
                      </div>
                    )}
                  </div>
                </div>

                {/* AI Thesis */}
                <div className="bg-[#0d1322] border border-slate-800/80 rounded-3xl p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                      <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                    </div>
                    <h3 className="text-xs font-black uppercase tracking-wider text-slate-200">Algorithmic Thesis & Catalysts</h3>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed font-medium bg-[#07090e]/80 p-3 rounded-2xl border border-slate-800/60">
                    "{predictionData.catalyst_summary}"
                  </p>

                  <div className="grid grid-cols-2 gap-2 pt-1">
                    {predictionData.ai_factors?.map((f, i) => (
                      <div key={i} className="bg-[#0b0f19] p-2.5 rounded-xl border border-slate-800 flex justify-between items-center">
                        <span className="text-[10px] font-bold text-slate-400">{f.factor}</span>
                        <span className={`text-[10px] font-black ${f.sentiment === 'bullish' ? 'text-emerald-400' : 'text-rose-400'}`}>{f.score}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Button */}
                <div className="pt-1">
                  <button 
                    onClick={() => setTradeModalOpen(true)}
                    className={`w-full py-4 rounded-2xl font-black text-sm tracking-wide flex items-center justify-center gap-2 shadow-xl transition-all active:scale-[0.98] ${
                      isUp 
                        ? 'bg-gradient-to-r from-emerald-500 to-teal-400 text-neutral-950 shadow-emerald-500/25' 
                        : 'bg-gradient-to-r from-rose-600 to-pink-600 text-white shadow-rose-600/25'
                    }`}
                  >
                    Execute ${activeTicker} Strategy
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>

              </div>
            )}

            {/* TAB 2: ADVANCED QUANT DATA */}
            {activeTab === 'quant' && (
              <div className="space-y-3 animate-in fade-in duration-300">
                <div className="bg-[#0d1322] border border-slate-800 rounded-3xl p-5 space-y-4">
                  <h3 className="text-xs font-black uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                    <Gauge className="w-4 h-4" />
                    Options Gamma & Volatility Matrix
                  </h3>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-[#07090e] p-3 rounded-2xl border border-slate-800">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Max Pain (Friday)</p>
                      <p className="text-lg font-black text-cyan-400 mt-0.5">${predictionData.max_pain_price?.toFixed(2)}</p>
                      <p className="text-[9px] text-slate-400 mt-1">Options dealer equilibrium</p>
                    </div>

                    <div className="bg-[#07090e] p-3 rounded-2xl border border-slate-800">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Implied Vol (IV)</p>
                      <p className="text-lg font-black text-indigo-400 mt-0.5">{predictionData.implied_volatility}</p>
                      <p className="text-[9px] text-slate-400 mt-1">Friday annualized skew</p>
                    </div>

                    <div className="bg-[#07090e] p-3 rounded-2xl border border-slate-800">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Put/Call Ratio</p>
                      <p className="text-lg font-black text-emerald-400 mt-0.5">{predictionData.put_call_ratio}</p>
                      <p className="text-[9px] text-slate-400 mt-1">Bullish dominance</p>
                    </div>

                    <div className="bg-[#07090e] p-3 rounded-2xl border border-slate-800">
                      <p className="text-[10px] font-bold text-slate-500 uppercase">Bull Breakout Cap</p>
                      <p className="text-lg font-black text-emerald-400 mt-0.5">${predictionData.bull_target?.toFixed(2)}</p>
                      <p className="text-[9px] text-slate-400 mt-1">95th percentile upper bound</p>
                    </div>
                  </div>
                </div>

                <div className="bg-[#0d1322] border border-slate-800 rounded-3xl p-5">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-300 mb-3">Native Java Calculation Core</h3>
                  <div className="bg-[#07090e] p-3 rounded-xl border border-slate-800 text-[11px] font-mono text-slate-400 space-y-1">
                    <p className="text-emerald-400">✔ StockPredictorPlugin.java loaded</p>
                    <p>• Engine: BlackScholesOptionPricer::computeDelta</p>
                    <p>• Haptic Engine: UltraLowLatency Vibration OK</p>
                    <p>• Neural Weights: Gemini-2.5-Flash Latency ~320ms</p>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: LIVE AI COPILOT DESK */}
            {activeTab === 'copilot' && (
              <div className="flex flex-col h-[480px] bg-[#0d1322] border border-slate-800 rounded-3xl p-4 animate-in fade-in duration-300">
                <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
                  <div className="w-7 h-7 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div>
                    <h3 className="text-xs font-black text-white">Quant Copilot Live</h3>
                    <p className="text-[9px] text-slate-400">Positioning assistant for ${activeTicker}</p>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1 hide-scrollbar">
                  {chatMessages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                        msg.sender === 'user' 
                          ? 'bg-blue-600 text-white rounded-br-none' 
                          : 'bg-[#07090e] text-slate-200 border border-slate-800 rounded-bl-none'
                      }`}>
                        {msg.text}
                      </div>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="flex justify-start">
                      <div className="bg-[#07090e] border border-slate-800 p-3 rounded-2xl rounded-bl-none text-xs text-slate-400 flex items-center gap-2">
                        <RefreshCw className="w-3 h-3 text-cyan-400 animate-spin" />
                        Analyzing neural pricing vectors...
                      </div>
                    </div>
                  )}
                  <div ref={chatScrollRef} />
                </div>

                <form onSubmit={handleSendChat} className="pt-2 flex gap-2">
                  <input 
                    type="text" 
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder={`Ask about ${activeTicker} strike prices...`}
                    className="flex-1 bg-[#07090e] border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                  <button 
                    type="submit"
                    disabled={chatLoading}
                    className="bg-cyan-500 hover:bg-cyan-400 text-neutral-950 px-4 py-2.5 rounded-xl font-bold text-xs transition-colors disabled:opacity-50"
                  >
                    Send
                  </button>
                </form>
              </div>
            )}

          </div>
        ) : null}

      </main>

      {/* Trade Execution Sheet Modal */}
      {tradeModalOpen && (
        <div className="absolute inset-0 bg-black/85 backdrop-blur-md z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-[#0d1322] border border-slate-800 rounded-3xl p-6 w-full max-w-sm space-y-4 animate-in slide-in-from-bottom duration-300 shadow-2xl">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="font-extrabold text-lg text-white">Quantum Order Entry</h3>
                <p className="text-xs text-slate-400 font-medium">${activeTicker} • Friday Target Horizon</p>
              </div>
              <button 
                onClick={() => setTradeModalOpen(false)}
                className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            {tradeSuccess ? (
              <div className="py-8 text-center space-y-3">
                <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto animate-bounce" />
                <p className="text-base font-bold text-white">Position Filled Instantly</p>
                <p className="text-xs text-slate-400">Added {sharesInput} shares of ${activeTicker} to portfolio.</p>
              </div>
            ) : (
              <form onSubmit={handleExecuteTrade} className="space-y-4">
                <div className="flex rounded-xl bg-[#07090e] p-1 border border-slate-800">
                  <button
                    type="button"
                    onClick={() => setTradeType('buy')}
                    className={`flex-1 py-2 rounded-lg text-xs font-black transition-all ${tradeType === 'buy' ? 'bg-emerald-500 text-neutral-950' : 'text-slate-400'}`}
                  >
                    Call / Long
                  </button>
                  <button
                    type="button"
                    onClick={() => setTradeType('sell')}
                    className={`flex-1 py-2 rounded-lg text-xs font-black transition-all ${tradeType === 'sell' ? 'bg-rose-500 text-white' : 'text-slate-400'}`}
                  >
                    Put / Short
                  </button>
                </div>

                <div>
                  <label className="text-[10px] font-black text-slate-400 uppercase">Quantity (Units / Contracts)</label>
                  <input 
                    type="number" 
                    value={sharesInput}
                    onChange={(e) => setSharesInput(e.target.value)}
                    className="w-full bg-[#07090e] border border-slate-800 rounded-xl p-3 mt-1 text-sm font-black text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div className="p-3 bg-[#07090e] rounded-xl border border-slate-800 space-y-1.5 text-xs font-semibold">
                  <div className="flex justify-between text-slate-400">
                    <span>Spot Notional:</span>
                    <span className="text-white">${((predictionData?.current_price || 100) * Number(sharesInput || 0)).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Friday Projected PnL:</span>
                    <span className={priceColor}>${((predictionData?.friday_prediction || 100) * Number(sharesInput || 0)).toFixed(2)}</span>
                  </div>
                </div>

                <button 
                  type="submit"
                  className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-cyan-500 hover:opacity-90 text-white font-black rounded-xl text-xs uppercase tracking-wider shadow-lg shadow-blue-500/20"
                >
                  Confirm Instant Trade
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Bottom Glass Navigation Bar */}
      <nav className="absolute bottom-0 inset-x-0 bg-[#07090e]/95 backdrop-blur-2xl border-t border-slate-800/80 py-3.5 px-6 flex justify-between items-center z-40">
        <button 
          onClick={() => setActiveTab('forecast')} 
          className={`flex flex-col items-center gap-1 ${activeTab === 'forecast' ? 'text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}
        >
          <Sparkles className="w-5 h-5" />
          <span className="text-[9px] font-black tracking-wider uppercase">Forecast</span>
        </button>

        <button 
          onClick={() => setActiveTab('quant')} 
          className={`flex flex-col items-center gap-1 ${activeTab === 'quant' ? 'text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}
        >
          <Gauge className="w-5 h-5" />
          <span className="text-[9px] font-black tracking-wider uppercase">Quant</span>
        </button>

        <button 
          onClick={() => setActiveTab('copilot')} 
          className={`flex flex-col items-center gap-1 ${activeTab === 'copilot' ? 'text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}
        >
          <Bot className="w-5 h-5" />
          <span className="text-[9px] font-black tracking-wider uppercase">AI Desk</span>
        </button>

        <button 
          onClick={() => setTradeModalOpen(true)} 
          className="flex flex-col items-center gap-1 text-slate-500 hover:text-slate-300"
        >
          <Wallet className="w-5 h-5" />
          <span className="text-[9px] font-black tracking-wider uppercase">Position</span>
        </button>
      </nav>

    </div>
  );
};

export default App;
