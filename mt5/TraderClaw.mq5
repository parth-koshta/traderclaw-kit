//+------------------------------------------------------------------+
//| TraderClaw.mq5 (kit edition)                                     |
//|                                                                  |
//| A background MT5 service with three jobs:                        |
//|  1. Export: candles M1-D1, quotes, open positions and orders,    |
//|     account and deal history to MQL5\Files\traderclaw\, so your  |
//|     scripts and AI agent read real numbers, not screenshots.     |
//|  2. Draw: the lines listed in traderclaw\draw*.csv (the kit's    |
//|     engine writes draw_levels.csv) on every open chart of the    |
//|     symbol. Objects are named TCK_..., so your own drawings are  |
//|     never touched.                                               |
//|  3. Push: every new line of traderclaw\notify.tsv goes to your   |
//|     phone as an MT5 push notification (MetaQuotes ID).           |
//|                                                                  |
//| READ-ONLY BY DESIGN: it contains no trading functions and cannot |
//| open, modify or close positions or orders. Keep it that way.     |
//|                                                                  |
//| Install: copy to <MT5 data folder>\MQL5\Services\, open it in    |
//| MetaEditor and Compile (F7), then in MT5: Navigator > Services > |
//| TraderClaw > right-click > Add Service.                          |
//| MIT licence. Information only, not financial advice.            |
//+------------------------------------------------------------------+
#property service
#property version     "1.00"
#define TC_VERSION    "1.00"                    // keep equal to #property version: written to status.txt
#property description "TraderClaw kit: read-only export, chart levels and phone push (no trading functions)"

input string InpSymbols       = "EURUSD,GBPUSD,XAUUSD"; // Symbols (comma separated; traderclaw\symbols.txt from the engine overrides)
input int    InpIntervalSec   = 15;                     // Export interval, seconds
input bool   InpPush          = true;                   // Send notify.tsv messages as phone push notifications
input bool   InpDesktopAlerts = false;                  // Also show them as MT5 pop-ups
input int    InpFontSize      = 8;                      // Label font size
input int    InpBarsM1        = 1440;                   // M1 bars (~1 day)
input int    InpBarsM5        = 1152;                   // M5 bars (~4 days)
input int    InpBarsM15       = 960;                    // M15 bars (~10 days)
input int    InpBarsH1        = 720;                    // H1 bars (~1 month)
input int    InpBarsH4        = 540;                    // H4 bars (~3 months)
input int    InpBarsD1        = 400;                    // D1 bars (~1.5 years)

const string          DIR    = "traderclaw";
const string          PREFIX = "TCK_";
const ENUM_TIMEFRAMES TFS[6] = {PERIOD_M1, PERIOD_M5, PERIOD_M15, PERIOD_H1, PERIOD_H4, PERIOD_D1};
const string          TFN[6] = {"M1", "M5", "M15", "H1", "H4", "D1"};

string   g_errors = "";
string   g_key    = "";      // <server>_<last 4 digits of login>: names the per-account history file
string   g_queue[];          // push messages waiting (MT5 allows only a few per minute)
datetime g_lastPush = 0;
string   g_pushError = "";
long     g_notifySent = -1;  // newest notify.tsv id already pushed

//+------------------------------------------------------------------+
//| Files are written to <name>.tmp and renamed, so a reader never   |
//| sees a half-written file.                                        |
//+------------------------------------------------------------------+
int OpenTmp(const string name)
  {
   int h = FileOpen(DIR + "\\" + name + ".tmp", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      g_errors += name + ": FileOpen " + IntegerToString(GetLastError()) + "; ";
   return h;
  }

void Commit(const int h, const string name)
  {
   FileClose(h);
   if(!FileMove(DIR + "\\" + name + ".tmp", 0, DIR + "\\" + name, FILE_REWRITE))
      g_errors += name + ": FileMove " + IntegerToString(GetLastError()) + "; ";
  }

string Csv(string s)
  {
   StringReplace(s, ",", ";");
   StringReplace(s, "\n", " ");
   return s;
  }

string Ts(const datetime t)
  {
   return t == 0 ? "" : TimeToString(t, TIME_DATE | TIME_SECONDS);
  }

string EnumName(string s, const string prefix)
  {
   StringReplace(s, prefix, "");
   StringToLower(s);
   return s;
  }

string AccountKey()
  {
   string login = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   string key = AccountInfoString(ACCOUNT_SERVER) + "_" + StringSubstr(login, (int)MathMax(0, StringLen(login) - 4));
   string out = "";
   for(int i = 0; i < StringLen(key); i++)
     {
      ushort c = StringGetCharacter(key, i);
      bool ok = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '-' || c == '_';
      out += ok ? ShortToString(c) : "_";
     }
   return out;
  }

// The engine writes traderclaw\symbols.txt from config.json, so changing symbols needs no MT5 step.
void ParseSymbols(string &out[])
  {
   string list = InpSymbols;
   int h = FileOpen(DIR + "\\symbols.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE)
     {
      string line = FileReadString(h);
      FileClose(h);
      StringReplace(line, "\r", "");
      if(StringLen(line) > 0)
         list = line;
     }
   string parts[];
   int n = StringSplit(list, ',', parts);
   ArrayResize(out, 0);
   for(int i = 0; i < n; i++)
     {
      string s = parts[i];
      StringTrimLeft(s);
      StringTrimRight(s);
      if(s == "")
         continue;
      int k = ArraySize(out);
      ArrayResize(out, k + 1);
      out[k] = s;
     }
  }

int BarsFor(const int i)
  {
   switch(i)
     {
      case 0: return InpBarsM1;
      case 1: return InpBarsM5;
      case 2: return InpBarsM15;
      case 3: return InpBarsH1;
      case 4: return InpBarsH4;
      default: return InpBarsD1;
     }
  }

//+------------------------------------------------------------------+
//| 1. EXPORT                                                        |
//+------------------------------------------------------------------+
void ExportCandles(const string sym)
  {
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   for(int i = 0; i < ArraySize(TFS); i++)
     {
      MqlRates r[];
      ArraySetAsSeries(r, false);
      int n = CopyRates(sym, TFS[i], 0, BarsFor(i), r);
      if(n <= 0)
        {
         g_errors += sym + "_" + TFN[i] + ": CopyRates " + IntegerToString(GetLastError()) + "; ";
         continue;
        }
      string name = sym + "_" + TFN[i] + ".csv";
      int h = OpenTmp(name);
      if(h == INVALID_HANDLE)
         continue;
      // Oldest first; the last row is the candle still forming. Times are server time.
      FileWriteString(h, "time,open,high,low,close,tick_volume,spread\n");
      for(int k = 0; k < n; k++)
         FileWriteString(h, StringFormat("%s,%s,%s,%s,%s,%I64d,%d\n",
                                         TimeToString(r[k].time, TIME_DATE | TIME_MINUTES),
                                         DoubleToString(r[k].open, digits), DoubleToString(r[k].high, digits),
                                         DoubleToString(r[k].low, digits), DoubleToString(r[k].close, digits),
                                         r[k].tick_volume, r[k].spread));
      Commit(h, name);
     }
  }

void ExportQuotes(const string &syms[])
  {
   int h = OpenTmp("quotes.csv");
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, "symbol,bid,ask,spread_points,digits,point,tick_value,tick_size,contract_size,tick_time\n");
   for(int i = 0; i < ArraySize(syms); i++)
     {
      MqlTick t;
      if(!SymbolInfoTick(syms[i], t))
         continue;
      int digits = (int)SymbolInfoInteger(syms[i], SYMBOL_DIGITS);
      FileWriteString(h, StringFormat("%s,%s,%s,%d,%d,%s,%.6f,%s,%.2f,%s\n", syms[i],
                                      DoubleToString(t.bid, digits), DoubleToString(t.ask, digits),
                                      (int)SymbolInfoInteger(syms[i], SYMBOL_SPREAD), digits,
                                      DoubleToString(SymbolInfoDouble(syms[i], SYMBOL_POINT), digits),
                                      SymbolInfoDouble(syms[i], SYMBOL_TRADE_TICK_VALUE),
                                      DoubleToString(SymbolInfoDouble(syms[i], SYMBOL_TRADE_TICK_SIZE), digits),
                                      SymbolInfoDouble(syms[i], SYMBOL_TRADE_CONTRACT_SIZE), Ts(t.time)));
     }
   Commit(h, "quotes.csv");
  }

void ExportPositions()
  {
   int h = OpenTmp("positions.csv");
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, "ticket,symbol,type,volume,price_open,sl,tp,price_current,profit,swap,time_open\n");
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      FileWriteString(h, StringFormat("%I64u,%s,%s,%.2f,%s,%s,%s,%s,%.2f,%.2f,%s\n", ticket, sym,
                                      PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "buy" : "sell",
                                      PositionGetDouble(POSITION_VOLUME),
                                      DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits),
                                      DoubleToString(PositionGetDouble(POSITION_SL), digits),
                                      DoubleToString(PositionGetDouble(POSITION_TP), digits),
                                      DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), digits),
                                      PositionGetDouble(POSITION_PROFIT), PositionGetDouble(POSITION_SWAP),
                                      Ts((datetime)PositionGetInteger(POSITION_TIME))));
     }
   Commit(h, "positions.csv");
  }

void ExportOrders()
  {
   int h = OpenTmp("orders.csv");
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, "ticket,symbol,type,volume,price,sl,tp,time_setup\n");
   for(int i = 0; i < OrdersTotal(); i++)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      string sym = OrderGetString(ORDER_SYMBOL);
      int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      FileWriteString(h, StringFormat("%I64u,%s,%s,%.2f,%s,%s,%s,%s\n", ticket, sym,
                                      EnumName(EnumToString((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE)), "ORDER_TYPE_"),
                                      OrderGetDouble(ORDER_VOLUME_CURRENT),
                                      DoubleToString(OrderGetDouble(ORDER_PRICE_OPEN), digits),
                                      DoubleToString(OrderGetDouble(ORDER_SL), digits),
                                      DoubleToString(OrderGetDouble(ORDER_TP), digits),
                                      Ts((datetime)OrderGetInteger(ORDER_TIME_SETUP))));
     }
   Commit(h, "orders.csv");
  }

void ExportAccount()
  {
   int h = OpenTmp("account.csv");
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, "company,server,account_key,currency,balance,equity,profit,margin,margin_free\n");
   FileWriteString(h, StringFormat("%s,%s,%s,%s,%.2f,%.2f,%.2f,%.2f,%.2f\n", Csv(AccountInfoString(ACCOUNT_COMPANY)),
                                   Csv(AccountInfoString(ACCOUNT_SERVER)), g_key, AccountInfoString(ACCOUNT_CURRENCY),
                                   AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY),
                                   AccountInfoDouble(ACCOUNT_PROFIT), AccountInfoDouble(ACCOUNT_MARGIN),
                                   AccountInfoDouble(ACCOUNT_MARGIN_FREE)));
   Commit(h, "account.csv");
  }

// Every deal on the logged-in account. reason (client/sl/tp/so/mobile/web/expert) tells how a position closed.
void ExportHistory()
  {
   if(!HistorySelect(0, TimeCurrent() + 86400))
     {
      g_errors += "HistorySelect " + IntegerToString(GetLastError()) + "; ";
      return;
     }
   string name = "history_" + g_key + ".csv";
   int h = OpenTmp(name);
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, "deal,position,time,symbol,type,entry,volume,price,sl,tp,profit,commission,swap,fee,reason,comment\n");
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      string sym = HistoryDealGetString(d, DEAL_SYMBOL);
      int digits = sym == "" ? 2 : (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      FileWriteString(h, StringFormat("%I64u,%I64d,%s,%s,%s,%s,%.2f,%s,%s,%s,%.2f,%.2f,%.2f,%.2f,%s,%s\n", d,
                                      HistoryDealGetInteger(d, DEAL_POSITION_ID),
                                      Ts((datetime)HistoryDealGetInteger(d, DEAL_TIME)), sym,
                                      EnumName(EnumToString((ENUM_DEAL_TYPE)HistoryDealGetInteger(d, DEAL_TYPE)), "DEAL_TYPE_"),
                                      EnumName(EnumToString((ENUM_DEAL_ENTRY)HistoryDealGetInteger(d, DEAL_ENTRY)), "DEAL_ENTRY_"),
                                      HistoryDealGetDouble(d, DEAL_VOLUME),
                                      DoubleToString(HistoryDealGetDouble(d, DEAL_PRICE), digits),
                                      DoubleToString(HistoryDealGetDouble(d, DEAL_SL), digits),
                                      DoubleToString(HistoryDealGetDouble(d, DEAL_TP), digits),
                                      HistoryDealGetDouble(d, DEAL_PROFIT), HistoryDealGetDouble(d, DEAL_COMMISSION),
                                      HistoryDealGetDouble(d, DEAL_SWAP), HistoryDealGetDouble(d, DEAL_FEE),
                                      EnumName(EnumToString((ENUM_DEAL_REASON)HistoryDealGetInteger(d, DEAL_REASON)), "DEAL_REASON_"),
                                      Csv(HistoryDealGetString(d, DEAL_COMMENT))));
     }
   Commit(h, name);
  }

void ExportStatus(const string &syms[])
  {
   int h = OpenTmp("status.txt");
   if(h == INVALID_HANDLE)
      return;
   datetime server = TimeTradeServer(), gmt = TimeGMT();
   string list = "";
   for(int i = 0; i < ArraySize(syms); i++)
      list += (i > 0 ? "," : "") + syms[i];
   FileWriteString(h, "exported_server_time=" + Ts(server) + "\n");
   FileWriteString(h, "exported_gmt_time=" + Ts(gmt) + "\n");
   FileWriteString(h, "server_gmt_offset_hours=" + DoubleToString((double)(server - gmt) / 3600.0, 1) + "\n");
   FileWriteString(h, "interval_sec=" + IntegerToString(InpIntervalSec) + "\n");
   FileWriteString(h, "account_key=" + g_key + "\n");
   FileWriteString(h, "account_company=" + Csv(AccountInfoString(ACCOUNT_COMPANY)) + "\n");
   FileWriteString(h, "account_server=" + AccountInfoString(ACCOUNT_SERVER) + "\n");
   FileWriteString(h, "symbols=" + list + "\n");
   FileWriteString(h, "service_version=" + TC_VERSION + "\n");
   FileWriteString(h, "push=" + (InpPush ? (TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED) ? "on" : "off in MT5 settings") : "off") +
                   (g_pushError != "" ? " (" + g_pushError + ")" : "") + "\n");
   FileWriteString(h, "errors=" + g_errors + "\n");
   Commit(h, "status.txt");
   g_errors = "";
  }

//+------------------------------------------------------------------+
//| 2. DRAW: traderclaw\draw*.csv                                    |
//|   version,<n>                                                    |
//|   symbol,type,name,time1,price1,time2,price2,color,style,width,  |
//|          timeframes,text                                         |
//| type: hline | rect | trend | vline | text | arrow_up | arrow_down|
//| A chart is redrawn only when the file's version changes.        |
//+------------------------------------------------------------------+
long   g_drawCharts[];
string g_drawFiles[];
int    g_drawVer[];
bool   g_drawCleaned = false;

int HexVal(const ushort c)
  {
   if(c >= '0' && c <= '9') return c - '0';
   if(c >= 'a' && c <= 'f') return c - 'a' + 10;
   if(c >= 'A' && c <= 'F') return c - 'A' + 10;
   return 0;
  }

color HexColor(const string s)
  {
   if(StringLen(s) != 7)
      return clrDarkOrange;
   int r = HexVal(StringGetCharacter(s, 1)) * 16 + HexVal(StringGetCharacter(s, 2));
   int g = HexVal(StringGetCharacter(s, 3)) * 16 + HexVal(StringGetCharacter(s, 4));
   int b = HexVal(StringGetCharacter(s, 5)) * 16 + HexVal(StringGetCharacter(s, 6));
   return (color)((b << 16) | (g << 8) | r);
  }

long Timeframes(const string s)
  {
   if(s == "" || s == "all")
      return OBJ_ALL_PERIODS;
   string t[];
   int n = StringSplit(s, '|', t);
   long f = 0;
   for(int i = 0; i < n; i++)
     {
      if(t[i] == "M1")  f |= OBJ_PERIOD_M1;
      if(t[i] == "M5")  f |= OBJ_PERIOD_M5;
      if(t[i] == "M15") f |= OBJ_PERIOD_M15;
      if(t[i] == "M30") f |= OBJ_PERIOD_M30;
      if(t[i] == "H1")  f |= OBJ_PERIOD_H1;
      if(t[i] == "H4")  f |= OBJ_PERIOD_H4;
      if(t[i] == "D1")  f |= OBJ_PERIOD_D1;
      if(t[i] == "W1")  f |= OBJ_PERIOD_W1;
      if(t[i] == "MN")  f |= OBJ_PERIOD_MN1;
     }
   return f == 0 ? OBJ_ALL_PERIODS : f;
  }

int ReadDrawFile(const string file, string &rows[])
  {
   ArrayResize(rows, 0);
   int h = FileOpen(DIR + "\\" + file, FILE_READ | FILE_TXT | FILE_ANSI, 0, CP_UTF8);
   if(h == INVALID_HANDLE)
      return -1;
   int version = -1;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      StringReplace(line, "\r", "");
      if(line == "" || StringFind(line, "symbol,") == 0)
         continue;
      if(StringFind(line, "version,") == 0)
        {
         version = (int)StringToInteger(StringSubstr(line, 8));
         continue;
        }
      int k = ArraySize(rows);
      ArrayResize(rows, k + 1);
      rows[k] = line;
     }
   FileClose(h);
   return version;
  }

void StyleObject(const long ch, const string name, const color clr, const long tfs, const string text)
  {
   ObjectSetInteger(ch, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(ch, name, OBJPROP_TIMEFRAMES, tfs);
   ObjectSetInteger(ch, name, OBJPROP_SELECTABLE, true);
   ObjectSetInteger(ch, name, OBJPROP_HIDDEN, false);
   ObjectSetString(ch, name, OBJPROP_TOOLTIP, text);
  }

void DrawRow(const long ch, const string prefix, const string row)
  {
   string f[];
   int n = StringSplit(row, ',', f);
   if(n < 12 || f[0] != ChartSymbol(ch))
      return;
   string text = f[11];
   for(int i = 12; i < n; i++)
      text += "," + f[i];
   string   type  = f[1];
   string   name  = prefix + f[2];
   datetime t1    = f[3] == "" ? TimeCurrent() : StringToTime(f[3]);
   double   p1    = StringToDouble(f[4]);
   datetime t2    = f[5] == "" ? TimeCurrent() : StringToTime(f[5]);
   double   p2    = StringToDouble(f[6]);
   color    clr   = HexColor(f[7]);
   int      style = f[8] == "dash" ? STYLE_DASH : (f[8] == "dot" ? STYLE_DOT : STYLE_SOLID);
   int      width = (int)MathMax(1, StringToInteger(f[9]));
   long     tfs   = Timeframes(f[10]);
   bool ok = false;
   if(type == "hline")           ok = ObjectCreate(ch, name, OBJ_HLINE, 0, 0, p1);
   else if(type == "rect")       ok = ObjectCreate(ch, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   else if(type == "trend")      ok = ObjectCreate(ch, name, OBJ_TREND, 0, t1, p1, t2, p2);
   else if(type == "vline")      ok = ObjectCreate(ch, name, OBJ_VLINE, 0, t1, 0);
   else if(type == "text")       ok = ObjectCreate(ch, name, OBJ_TEXT, 0, t1, p1);
   else if(type == "arrow_up")   ok = ObjectCreate(ch, name, OBJ_ARROW_UP, 0, t1, p1);
   else if(type == "arrow_down") ok = ObjectCreate(ch, name, OBJ_ARROW_DOWN, 0, t1, p1);
   if(!ok)
     {
      g_errors += "draw " + f[2] + ": " + IntegerToString(GetLastError()) + "; ";
      return;
     }
   StyleObject(ch, name, clr, tfs, text);
   ObjectSetInteger(ch, name, OBJPROP_STYLE, style);
   ObjectSetInteger(ch, name, OBJPROP_WIDTH, width);
   if(type == "rect")
     {
      ObjectSetInteger(ch, name, OBJPROP_FILL, style == STYLE_SOLID);   // dashed/dotted boxes are outlines
      ObjectSetInteger(ch, name, OBJPROP_BACK, true);
     }
   if(type == "trend")
      ObjectSetInteger(ch, name, OBJPROP_RAY_RIGHT, false);
   if(type == "text")
     {
      ObjectSetString(ch, name, OBJPROP_TEXT, text);
      ObjectSetInteger(ch, name, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetInteger(ch, name, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
      return;
     }
   // MT5 hides object descriptions by default, so lines and boxes get their label as a text object at time1.
   if(text == "" || type == "vline")
      return;
   string tn = name + "_t";
   if(ObjectCreate(ch, tn, OBJ_TEXT, 0, t1, type == "rect" ? MathMax(p1, p2) : p1))
     {
      StyleObject(ch, tn, clr, tfs, text);
      ObjectSetString(ch, tn, OBJPROP_TEXT, text);
      ObjectSetInteger(ch, tn, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetInteger(ch, tn, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
     }
  }

int DrawIndex(const long ch, const string file)
  {
   for(int i = 0; i < ArraySize(g_drawCharts); i++)
      if(g_drawCharts[i] == ch && g_drawFiles[i] == file)
         return i;
   int k = ArraySize(g_drawCharts);
   ArrayResize(g_drawCharts, k + 1);
   ArrayResize(g_drawFiles, k + 1);
   ArrayResize(g_drawVer, k + 1);
   g_drawCharts[k] = ch;
   g_drawFiles[k] = file;
   g_drawVer[k] = -2;   // never drawn
   return k;
  }

void DrawFile(const string file)
  {
   string rows[];
   int version = ReadDrawFile(file, rows);
   // The dot ends the file part, so draw_x.csv's prefix never matches draw_x_y.csv's objects.
   string prefix = PREFIX + StringSubstr(file, 0, StringLen(file) - 4) + ".";
   long ch = ChartFirst();
   while(ch >= 0)
     {
      int i = DrawIndex(ch, file);
      if(g_drawVer[i] != version)
        {
         ObjectsDeleteAll(ch, prefix);
         for(int r = 0; r < ArraySize(rows); r++)
            DrawRow(ch, prefix, rows[r]);
         g_drawVer[i] = version;
         ChartRedraw(ch);
        }
      ch = ChartNext(ch);
     }
  }

void DrawTick()
  {
   if(!g_drawCleaned)           // on start, clear every TCK_ object once (left over from deleted files)
     {
      long ch = ChartFirst();
      while(ch >= 0)
        {
         ObjectsDeleteAll(ch, PREFIX);
         ch = ChartNext(ch);
        }
      g_drawCleaned = true;
     }
   string file;
   long finder = FileFindFirst(DIR + "\\draw*.csv", file);
   if(finder == INVALID_HANDLE)
      return;
   do
      DrawFile(file);
   while(FileFindNext(finder, file));
   FileFindClose(finder);
  }

//+------------------------------------------------------------------+
//| 3. PUSH: traderclaw\notify.tsv (id, time, text). Pushes every id |
//| above the last one sent; on the first run it starts from the     |
//| newest id, so old messages are never replayed.                   |
//+------------------------------------------------------------------+
void NotifyFromFile()
  {
   string statePath = DIR + "\\notify_state.txt";
   if(g_notifySent < 0)
     {
      int sh = FileOpen(statePath, FILE_READ | FILE_TXT | FILE_ANSI);
      if(sh != INVALID_HANDLE)
        {
         g_notifySent = StringToInteger(FileReadString(sh));
         FileClose(sh);
        }
     }
   int h = FileOpen(DIR + "\\notify.tsv", FILE_READ | FILE_TXT | FILE_ANSI, 0, CP_UTF8);
   if(h == INVALID_HANDLE)
     {
      if(g_notifySent < 0)
         g_notifySent = 0;      // no queue yet: every future message is new
      return;
     }
   long newest = g_notifySent;
   bool first = g_notifySent < 0;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      StringReplace(line, "\r", "");
      string f[];
      if(StringSplit(line, '\t', f) < 3 || f[0] == "id")
         continue;
      long id = StringToInteger(f[0]);
      if(id <= newest)
         continue;
      newest = id;
      if(first)
         continue;
      Print("TraderClaw: ", f[2]);
      if(InpDesktopAlerts)
         Alert(f[2]);
      if(InpPush)
        {
         int q = ArraySize(g_queue);
         ArrayResize(g_queue, q + 1);
         g_queue[q] = StringSubstr(f[2], 0, 255);
        }
     }
   FileClose(h);
   if(newest != g_notifySent)
     {
      g_notifySent = newest;
      int sh = FileOpen(statePath, FILE_WRITE | FILE_TXT | FILE_ANSI);
      if(sh != INVALID_HANDLE)
        {
         FileWriteString(sh, IntegerToString(newest));
         FileClose(sh);
        }
     }
  }

// MT5 allows only a few pushes per minute, so they go out one at a time.
void FlushPush()
  {
   if(ArraySize(g_queue) == 0 || TimeLocal() - g_lastPush < 7)
      return;
   g_lastPush = TimeLocal();
   if(!TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))
     {
      g_pushError = "push notifications are off: Tools > Options > Notifications";
      ArrayResize(g_queue, 0);
      return;
     }
   if(SendNotification(g_queue[0]))
      g_pushError = "";
   else
      g_pushError = "SendNotification " + IntegerToString(GetLastError());
   ArrayRemove(g_queue, 0, 1);
  }

//+------------------------------------------------------------------+
void OnStart()
  {
   string syms[];
   ParseSymbols(syms);
   FolderCreate(DIR, 0);
   uint lastExport = 0, lastDraw = 0;
   long lastMinute = -1;
   bool first = true;
   while(!IsStopped())
     {
      uint ms = GetTickCount();
      g_key = AccountKey();
      // Export right after every candle close (the server minute rolling over), not only on the interval.
      datetime srv = TimeTradeServer();
      long minute = (long)srv / 60;
      bool newMinute = lastMinute >= 0 && minute != lastMinute && (srv % 60) >= 1;
      if(lastMinute < 0 || newMinute)
         lastMinute = minute;
      if(first || ms - lastDraw >= 5000)
        {
         DrawTick();
         lastDraw = ms;
        }
      if(first || newMinute || ms - lastExport >= (uint)InpIntervalSec * 1000)
        {
         ParseSymbols(syms);
         for(int i = 0; i < ArraySize(syms); i++)
           {
            if(!SymbolSelect(syms[i], true))
              {
               g_errors += syms[i] + ": symbol not found (check the exact name in Market Watch); ";
               continue;
              }
            ExportCandles(syms[i]);
           }
         ExportQuotes(syms);
         ExportPositions();
         ExportOrders();
         ExportAccount();
         ExportHistory();
         ExportStatus(syms);
         lastExport = ms;
        }
      NotifyFromFile();
      FlushPush();
      first = false;
      Sleep(250);               // short sleeps, so stopping the service is instant
     }
   // Stopping (or removing) the service removes its lines, which would go stale; starting it draws them again.
   long ch = ChartFirst();
   while(ch >= 0)
     {
      ObjectsDeleteAll(ch, PREFIX);
      ChartRedraw(ch);
      ch = ChartNext(ch);
     }
  }
//+------------------------------------------------------------------+
