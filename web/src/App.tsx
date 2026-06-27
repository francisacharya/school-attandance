import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Link, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import {
  Users, BookOpen, Calendar, Clock, MapPin,
  LogOut, Plus, Trash2, Edit2,
  CheckCircle, XCircle, Save,
  FileText, Download, Menu, X,
  Filter, MessageSquare, Smartphone,
  LayoutDashboard, ClipboardCheck, Home, BarChart3,
  Layers as Layer, Settings as SettingsIcon, Plane as PlaneIcon
} from 'lucide-react';
import QRScanner from './components/QRScanner';
import { QRCodeSVG } from 'qrcode.react';
import NepaliDateClass from 'nepali-date-converter';
// Robust check for different module formats (ESM vs CJS)
const NepaliDate: any = (typeof (NepaliDateClass as any) === 'function') 
  ? NepaliDateClass 
  : (NepaliDateClass as any).default || NepaliDateClass;

const NEPALI_MONTHS = [
  "Baisakh", "Jestha", "Ashad", "Shrawan", "Bhadra", "Ashwin",
  "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
];

/**
 * Isolated library logic to prevent Firefox XrayWrapper errors.
 * Returns only serializable primitives.
 */
const getNepaliMonthData = (year: number, month: number) => {
  try {
    const d = new (NepaliDate as any)(year, month, 1);
    const today = new (NepaliDate as any)();
    
    return {
      daysInMonth: Number(d.getDaysInMonth()),
      firstDay: Number(d.getDay()), // 0=Sun
      todayYear: Number(today.getYear()),
      todayMonth: Number(today.getMonth()),
      todayDay: Number(today.getDayOfMonth())
    };
  } catch (e) {
    return { daysInMonth: 30, firstDay: 0, todayYear: 2081, todayMonth: 0, todayDay: 1 };
  }
};

// Utility to convert AD YYYY-MM-DD to BS YYYY-MM-DD
const adToBs = (adStr: string) => {
  if (!adStr) return "";
  try {
    const jsDate = new Date(adStr);
    if (isNaN(jsDate.getTime())) return adStr;
    const d = new (NepaliDate as any)(jsDate);
    return String(d.format('YYYY-MM-DD'));
  } catch (e) { return adStr; }
};

// Utility to convert BS YYYY-MM-DD to AD YYYY-MM-DD
const bsToAd = (bsStr: string) => {
  if (!bsStr) return "";
  try {
    const parts = bsStr.split('-').map(Number);
    if (parts.length !== 3) return bsStr;
    const d = new (NepaliDate as any)(parts[0], parts[1] - 1, parts[2]);
    const jsDate = d.getJsDate();
    return jsDate.toISOString().split('T')[0];
  } catch (e) { return bsStr; }
};

// Static Nepali calendar lookup — avoids any library call for day counts.
// Data sourced from the standard BS calendar; covers years 2000–2090.
const BS_DAYS: Record<number, number[]> = {
  2000:[30,32,31,32,31,30,30,30,29,30,29,31],2001:[31,31,32,31,31,31,30,29,30,29,30,30],
  2002:[31,31,32,32,31,30,30,29,30,29,30,30],2003:[31,32,31,32,31,30,30,30,29,29,30,31],
  2004:[30,32,31,32,31,30,30,30,29,30,29,31],2005:[31,31,32,31,31,31,30,29,30,29,30,30],
  2006:[31,31,32,32,31,30,30,29,30,29,30,30],2007:[31,32,31,32,31,30,30,30,29,29,30,31],
  2008:[31,31,31,32,31,31,29,30,30,29,29,31],2009:[31,31,32,31,31,31,30,29,30,29,30,30],
  2010:[31,31,32,32,31,30,30,29,30,29,30,30],2011:[31,32,31,32,31,30,30,30,29,29,30,31],
  2012:[31,31,31,32,31,31,29,30,30,29,30,30],2013:[31,31,32,31,31,31,30,29,30,29,30,30],
  2014:[31,31,32,32,31,30,30,29,30,29,30,30],2015:[31,32,31,32,31,30,30,30,29,29,30,31],
  2016:[31,31,31,32,31,31,29,30,30,29,30,30],2017:[31,31,32,31,31,31,30,29,30,29,30,30],
  2018:[31,32,31,32,31,30,30,29,30,29,30,30],2019:[31,32,31,32,31,30,30,30,29,30,29,31],
  2020:[31,31,31,32,31,31,30,29,30,29,30,30],2021:[31,31,32,31,31,31,30,29,30,29,30,30],
  2022:[31,32,31,32,31,30,30,30,29,29,30,30],2023:[31,32,31,32,31,30,30,30,29,30,29,31],
  2024:[31,31,31,32,31,31,30,29,30,29,30,30],2025:[31,31,32,31,31,31,30,29,30,29,30,30],
  2026:[31,32,31,32,31,30,30,30,29,29,30,31],2027:[30,32,31,32,31,30,30,30,29,30,29,31],
  2028:[31,31,32,31,31,31,30,29,30,29,30,30],2029:[31,31,32,31,32,30,30,29,30,29,30,30],
  2030:[31,32,31,32,31,30,30,30,29,29,30,31],2031:[31,31,31,32,31,31,30,29,30,29,30,30],
  2032:[31,31,32,31,31,31,30,29,30,29,30,30],2033:[31,32,31,32,31,30,30,30,29,29,30,30],
  2034:[31,32,31,32,31,30,30,30,29,30,29,31],2035:[31,31,31,32,31,31,30,29,30,29,30,30],
  2036:[31,31,32,31,31,31,30,29,30,29,30,30],2037:[31,32,31,32,31,30,30,30,29,29,30,31],
  2038:[31,31,31,32,31,31,29,30,30,29,30,30],2039:[31,31,32,31,31,31,30,29,30,29,30,30],
  2040:[31,32,31,32,31,30,30,30,29,29,30,31],2041:[31,31,31,32,31,31,29,30,30,29,30,30],
  2042:[31,31,32,31,31,31,30,29,30,29,30,30],2043:[31,31,32,32,31,30,30,29,30,29,30,30],
  2044:[31,32,31,32,31,30,30,30,29,29,30,31],2045:[31,31,31,32,31,31,30,29,30,29,30,30],
  2046:[31,31,32,31,31,31,30,29,30,29,30,30],2047:[31,32,31,32,31,30,30,30,29,29,30,30],
  2048:[31,32,31,32,31,30,30,30,29,30,29,31],2049:[31,31,31,32,31,31,30,29,30,29,30,30],
  2050:[31,31,32,31,31,31,30,29,30,29,30,30],2051:[31,32,31,32,31,30,30,30,29,29,30,30],
  2052:[31,32,31,32,31,30,30,30,29,30,29,31],2053:[31,31,31,32,31,31,30,29,30,29,30,30],
  2054:[31,31,32,31,31,31,30,29,30,29,30,30],2055:[31,32,31,32,31,30,30,30,29,29,30,31],
  2056:[31,31,31,32,31,31,30,29,30,29,30,30],2057:[31,31,32,31,31,31,30,29,30,29,30,30],
  2058:[31,32,31,32,31,30,30,29,30,29,30,30],2059:[31,32,31,32,31,30,30,30,29,29,30,31],
  2060:[31,31,31,32,31,31,30,29,30,29,30,30],2061:[31,31,32,31,31,31,30,29,30,29,30,30],
  2062:[31,32,31,32,31,30,30,30,29,29,30,30],2063:[31,32,31,32,31,30,30,30,29,30,29,31],
  2064:[31,31,31,32,31,31,30,29,30,29,30,30],2065:[31,31,32,31,31,32,29,30,30,29,29,31],
  2066:[31,32,31,32,31,30,30,29,30,29,30,30],2067:[31,32,31,32,31,30,30,30,29,29,30,31],
  2068:[31,31,31,32,31,31,30,29,30,29,30,30],2069:[31,31,32,31,31,31,30,29,30,29,30,30],
  2070:[31,32,31,32,31,30,30,30,29,29,30,31],2071:[31,31,31,32,31,31,30,29,30,29,30,30],
  2072:[31,31,32,31,31,32,29,30,29,30,29,31],2073:[31,32,31,32,31,30,30,29,30,29,30,30],
  2074:[31,32,31,32,31,30,30,30,29,29,30,31],2075:[31,31,31,32,31,31,30,29,30,29,30,30],
  2076:[31,31,32,31,31,31,30,29,30,29,30,30],2077:[31,32,31,32,31,30,30,30,29,29,30,30],
  2078:[31,32,31,32,31,30,30,30,29,30,29,31],2079:[31,31,31,32,31,31,30,29,30,29,30,30],
  2080:[31,31,32,31,31,31,30,29,30,29,30,30],2081:[31,31,32,32,31,30,30,29,30,29,30,30],
  2082:[31,32,31,32,31,30,30,30,29,29,30,31],2083:[31,31,31,32,31,31,30,29,30,29,30,30],
  2084:[31,31,32,31,31,31,30,29,30,29,30,30],2085:[31,32,31,32,31,30,30,30,29,29,30,30],
  2086:[31,32,31,32,31,30,30,30,29,30,29,31],2087:[31,31,31,32,31,31,30,29,30,29,30,30],
  2088:[31,31,32,31,31,31,30,29,30,29,30,30],2089:[31,32,31,32,31,30,30,30,29,29,30,30],
  2090:[31,32,31,32,31,30,30,30,29,30,29,31],
};

// Returns an array of AD date strings (YYYY-MM-DD) for every day in a given BS year/month.
// Uses static lookup — no library calls needed for day count.
const getNepaliMonthDaysAD = (year: number, month: number): string[] => {
  const monthDays = BS_DAYS[year];
  if (!monthDays) {
    console.warn(`No BS calendar data for year ${year}`);
    return [];
  }
  const total = monthDays[month - 1];
  if (!total) return [];

  const days: string[] = [];
  for (let i = 1; i <= total; i++) {
    const adStr = bsToAd(`${year}-${String(month).padStart(2,'0')}-${String(i).padStart(2,'0')}`);
    if (adStr) days.push(adStr);
  }
  return days;
};

const NepaliDatePicker = ({ value, onChange, placeholder, required }: { value: string, onChange: (val: string) => void, placeholder?: string, required?: boolean }) => {
  const [show, setShow] = useState(false);
  
  // Store view state as numbers for stability
  const [viewYear, setViewYear] = useState(() => {
    try {
      if (value) {
        const parts = value.split('-').map(Number);
        if (!isNaN(parts[0])) return parts[0];
      }
    } catch {}
    try {
      const today = new (NepaliDate as any)();
      return Number(today.getYear());
    } catch { return 2081; }
  });
  
  const [viewMonth, setViewMonth] = useState(() => {
    try {
      if (value) {
        const parts = value.split('-').map(Number);
        if (!isNaN(parts[1])) return parts[1] - 1; // 0-indexed
      }
    } catch {}
    try {
      const today = new (NepaliDate as any)();
      return Number(today.getMonth());
    } catch { return 0; }
  });

  const years = Array.from({ length: 150 }, (_, i) => 2000 + i);
  
  const handlePrevMonth = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((v: number) => v - 1);
    } else {
      setViewMonth((v: number) => v - 1);
    }
  };

  const handleNextMonth = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((v: number) => v + 1);
    } else {
      setViewMonth((v: number) => v + 1);
    }
  };

  const monthData = React.useMemo(() => getNepaliMonthData(viewYear, viewMonth), [viewYear, viewMonth]);
  
  const days = [];
  for (let i = 0; i < monthData.firstDay; i++) days.push(null);
  for (let i = 1; i <= monthData.daysInMonth; i++) days.push(i);

  const isToday = (day: number) => {
    return monthData.todayYear === viewYear && monthData.todayMonth === viewMonth && monthData.todayDay === day;
  };

  const isSelected = (day: number) => {
    if (!value) return false;
    try {
      const parts = value.split('-').map(Number);
      return parts[0] === viewYear && parts[1] - 1 === viewMonth && parts[2] === day;
    } catch { return false; }
  };

  const selectDay = (day: number) => {
    const yStr = viewYear.toString();
    const mStr = (viewMonth + 1).toString().padStart(2, '0');
    const dStr = day.toString().padStart(2, '0');
    onChange(`${yStr}-${mStr}-${dStr}`);
    setShow(false);
  };

  return (
    <div className="nepali-datepicker-container">
      <div style={{ position: 'relative' }}>
        <input 
          type="text" 
          value={value} 
          onClick={() => setShow(!show)}
          readOnly
          placeholder={placeholder || "Select Date (BS)"}
          required={required}
          style={{ cursor: 'pointer', background: 'var(--input-bg)' }}
        />
        <Calendar 
          size={18} 
          style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray)', pointerEvents: 'none' }} 
        />
      </div>

      {show && (
        <>
          <div 
            style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 999 }} 
            onClick={() => setShow(false)} 
          />
          <div className="nepali-datepicker-popup glass-card">
            <div className="calendar-header">
              <button type="button" className="calendar-nav-btn" onClick={handlePrevMonth}><X size={14} style={{ transform: 'rotate(90deg)' }} /></button>
              <div style={{ display: 'flex', gap: '5px' }}>
                <select 
                  value={viewMonth} 
                  onChange={e => setViewMonth(parseInt(e.target.value))}
                  style={{ padding: '2px 8px', fontSize: '13px', width: 'auto', height: '30px', border: 'none', background: 'transparent', fontWeight: 600 }}
                >
                  {NEPALI_MONTHS.map((m, i) => <option key={i} value={i}>{m}</option>)}
                </select>
                <select 
                  value={viewYear} 
                  onChange={e => setViewYear(parseInt(e.target.value))}
                  style={{ padding: '2px 8px', fontSize: '13px', width: 'auto', height: '30px', border: 'none', background: 'transparent', fontWeight: 600 }}
                >
                  {years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
              <button type="button" className="calendar-nav-btn" onClick={handleNextMonth}><X size={14} style={{ transform: 'rotate(-100deg)' }} /></button>
            </div>

            <div className="calendar-grid">
              {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map(d => (
                <div key={d} className="calendar-day-label">{d}</div>
              ))}
              {days.map((day, i) => (
                <div 
                  key={i} 
                  className={`calendar-day ${day === null ? 'empty' : ''} ${day && isToday(day) ? 'today' : ''} ${day && isSelected(day) ? 'selected' : ''}`}
                  onClick={() => day && selectDay(day)}
                >
                  {day}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

const Sidebar = ({ role, onLogout }: { role: string, onLogout: () => void }) => {
  const [isOpen, setIsOpen] = useState(true);
  const location = useLocation();

  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard, path: '/' },
  ];

  if (role === 'admin') {
    menuItems.push({ name: 'Attendance', icon: ClipboardCheck, path: '/attendance' });
    menuItems.push({ name: 'Timetable', icon: Clock, path: '/admin/timetable' });
    menuItems.push({ name: 'Archived Classes', icon: Layer, path: '/admin/timetable/archived' });
    menuItems.push({ name: 'Users', icon: Users, path: '/admin/users' });
    menuItems.push({ name: 'Leave Requests', icon: PlaneIcon, path: '/admin/leaves' });
    
    // Group academic entities
    menuItems.push({ name: 'ACADEMIC', icon: LogOut, path: '#' }); // Category Header
    menuItems.push({ name: 'Sessions', icon: Calendar, path: '/admin/sessions' });
    menuItems.push({ name: 'Courses', icon: BookOpen, path: '/admin/courses' });
    menuItems.push({ name: 'Semesters', icon: Layer, path: '/admin/semesters' });
    menuItems.push({ name: 'Subjects', icon: BookOpen, path: '/admin/subjects' });
    menuItems.push({ name: 'Rooms', icon: Home, path: '/admin/rooms' });
    menuItems.push({ name: 'Periods', icon: Clock, path: '/admin/periods' });
    
    menuItems.push({ name: 'SYSTEM', icon: LogOut, path: '#' }); // Category Header
    menuItems.push({ name: 'Compliance', icon: FileText, path: '/admin/compliance' });
    menuItems.push({ name: 'Settings', icon: SettingsIcon, path: '/admin/settings' });
  } else if (role === 'teacher') {
    menuItems.push({ name: 'Day / Period wise Attendance', icon: ClipboardCheck, path: '/attendance' });
    menuItems.push({ name: 'Manage Bulk Attendance', icon: BarChart3, path: '/teacher/bulk-attendance' });
  } else if (role === 'student' || role === 'parent') {
    if (role === 'student') {
      menuItems.push({ name: 'Scan Class QR', icon: Smartphone, path: '/student/scan' });
    }
    menuItems.push({ name: 'Reports', icon: BarChart3, path: '/student/reports' });
    menuItems.push({ name: 'Leave', icon: PlaneIcon, path: '/student/leave' });
  }

  return (
    <div className="sidebar" style={{
      width: isOpen ? '280px' : '80px',
      height: '100vh',
      transition: 'width 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
      borderRight: '1px solid var(--glass-border)',
      background: 'var(--sidebar-bg)',
      backdropFilter: 'blur(16px)',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 10px',
      position: 'sticky',
      top: 0,
      fontSize: '14px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: isOpen ? 'space-between' : 'center', marginBottom: '20px' }}>
        {isOpen && <h2 style={{ fontSize: '16px', lineHeight: '1.3', fontWeight: 'bold', background: 'linear-gradient(to right, #6366f1, #ec4899)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Campus Management<br/>App</h2>}
        <button onClick={() => setIsOpen(!isOpen)} style={{ border: 'none', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer' }}>
          {isOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      <nav style={{ flex: 1, overflowY: 'auto' }}>
        <ul style={{ listStyle: 'none' }}>
          {menuItems.map((item, i) => {
            const isCategoryHeader = ['ACADEMIC', 'SYSTEM'].includes(item.name);
            if (isCategoryHeader) {
               return isOpen ? (
                 <li key={i} style={{ padding: '12px 12px 6px', fontSize: '10px', fontWeight: 800, color: 'var(--gray)', letterSpacing: '0.05em' }}>{item.name}</li>
               ) : <li key={i} style={{ margin: '8px 0', borderBottom: '1px solid var(--glass-border)' }} />;
            }
            const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
            return (
              <li key={i} style={{ marginBottom: '4px', position: 'relative' }}>
                <Link to={item.path} className={`sidebar-link ${isActive ? 'active' : ''}`} style={{ position: 'relative' }}>
                  {isActive && <div style={{ position: 'absolute', left: '-10px', top: '20%', bottom: '20%', width: '4px', background: 'var(--primary)', borderRadius: '0 4px 4px 0' }} />}
                  <item.icon size={18} style={{ opacity: isActive ? 1 : 0.7 }} />
                  {isOpen && <span style={{ fontWeight: isActive ? 700 : 500 }}>{item.name}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <button onClick={onLogout} className="sidebar-link" style={{ color: '#ef4444', border: 'none', background: 'transparent', cursor: 'pointer', marginTop: 'auto' }}>
        <LogOut size={20} />
        {isOpen && <span>Sign Out</span>}
      </button>
    </div>
  );
};

// --- Page Components ---

const LoginPage = ({ onLogin }: { onLogin: (user: any) => void }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await axios.post('http://localhost:8080/token', formData);
      const user = response.data;
      localStorage.setItem('token', user.access_token);
      localStorage.setItem('user', JSON.stringify(user));
      onLogin(user);
      navigate('/');
    } catch (err: any) {
      setError('Invalid credentials');
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: 'linear-gradient(135deg, #f0f4ff 0%, #f8fafc 50%, #fdf2f8 100%)' }}>
      <div className="glass-card fade-in" style={{ padding: '50px', width: '100%', maxWidth: '420px', textAlign: 'center' }}>
        <h1 style={{ marginBottom: '10px' }}>Sign In</h1>
        <p style={{ color: 'var(--gray)', marginBottom: '35px' }}>Attendance Portal Ecosystem</p>

        {error && <div style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '12px', borderRadius: '8px', marginBottom: '20px' }}>{error}</div>}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '20px', textAlign: 'left' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--gray)' }}>Username</label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Enter username" />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--gray)' }}>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          <button type="submit" className="btn-primary" style={{ marginTop: '10px' }}>Log In</button>
        </form>
      </div>
    </div>
  );
};

const AdminDashboard = () => {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await axios.get('http://localhost:8080/admin/stats', { headers: { Authorization: `Bearer ${token}` } });
        setStats(res.data);
      } catch (e) { console.error(e); }
    };
    fetch();
  }, []);

  const cards = [
    { title: 'Total Users', value: stats?.users, icon: Users, color: '#6366f1' },
    { title: 'Subjects', value: stats?.subjects, icon: BookOpen, color: '#ec4899' },
    { title: 'Today Records', value: stats?.today_records, icon: Calendar, color: '#3b82f6' },
  ];

  return (
    <div className="fade-in">
      <h1 style={{ marginBottom: '30px' }}>Admin Dashboard</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
        {cards.map((c, i) => (
          <div key={i} className="glass-card" style={{ padding: '30px', borderLeft: `5px solid ${c.color}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <p style={{ color: 'var(--gray)', fontSize: '14px', marginBottom: '5px' }}>{c.title}</p>
                <h2 style={{ fontSize: '36px' }}>{c.value || '--'}</h2>
              </div>
              <c.icon size={40} style={{ color: c.color, opacity: 0.8 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const TeacherDashboard = () => {
  const [schedule, setSchedule] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      const token = localStorage.getItem('token');
      const h = { headers: { Authorization: `Bearer ${token}` } };
      try {
        const [schedRes, statsRes] = await Promise.all([
          axios.get('http://localhost:8080/teacher/schedule', h),
          axios.get('http://localhost:8080/teacher/today-stats', h)
        ]);
        setSchedule(schedRes.data);
        setStats(statsRes.data);
      } catch (e) { console.error(e); }
    };
    load();
  }, []);

  const daysLabels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const dayShort   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  // JavaScript getDay(): 0=Sun, timetable: 0=Mon. Convert JS day to timetable day.
  const jsDay = new Date().getDay();
  const todayIdx = jsDay === 0 ? 6 : jsDay - 1;

  const todayClasses = schedule.filter(s => s.day_of_week === todayIdx);

  // Derive unique classes (distinct subject+session+period combos) from timetable schedule
  const uniqueClassMap = new Map<string, any>();
  schedule.forEach(cls => {
    const key = `${cls.subject_id}__${cls.session_id}__${cls.period_id}`;
    if (!uniqueClassMap.has(key)) {
      uniqueClassMap.set(key, { ...cls, days: [] });
    }
    uniqueClassMap.get(key)!.days.push(cls.day_of_week);
  });
  const assignedClasses = Array.from(uniqueClassMap.values());

  const handleTakeAttendance = (subjectId: number, sessionId: number | null, periodId: number) => {
    navigate(`/attendance?subject=${subjectId}&session=${sessionId || ''}&period=${periodId}`);
  };

  const statCards = [
    { label: "Today's Records", val: stats?.today_records ?? '--', color: '#6366f1', icon: ClipboardCheck },
    { label: 'Present', val: stats?.present ?? '--', color: '#10b981', icon: CheckCircle },
    { label: 'Absent', val: stats?.absent ?? '--', color: '#ef4444', icon: XCircle },
    { label: 'My Subjects', val: stats?.total_subjects ?? '--', color: '#3b82f6', icon: BookOpen },
  ];

  return (
    <div className="fade-in">
      <div style={{ marginBottom: '30px' }}>
        <h1 style={{ marginBottom: '4px' }}>Teacher Dashboard</h1>
        <p style={{ color: 'var(--gray)', fontSize: '14px', margin: 0 }}>
          {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '30px' }}>
        {statCards.map((c, i) => (
          <div key={i} className="glass-card" style={{ padding: '20px 24px', borderLeft: `4px solid ${c.color}`, cursor: 'default' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--gray)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{c.label}</div>
                <div style={{ fontSize: '32px', fontWeight: 700, marginTop: '4px' }}>{c.val}</div>
              </div>
              <c.icon size={32} style={{ color: c.color, opacity: 0.6 }} />
            </div>
          </div>
        ))}
      </div>

      {/* Assigned Classes - from Timetable */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BookOpen size={22} style={{ color: '#ec4899' }} />
          My Assigned Classes
          <span style={{ fontSize: '13px', fontWeight: 400, color: 'var(--gray)' }}>— from timetable</span>
        </h2>
        {assignedClasses.length === 0 ? (
          <div className="glass-card" style={{ padding: '30px', textAlign: 'center', color: 'var(--gray)' }}>
            No timetable classes assigned to you yet.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
            {assignedClasses.map((cls: any, i: number) => (
              <div key={i} className="glass-card" style={{
                padding: '20px', borderLeft: '4px solid #ec4899',
                display: 'flex', flexDirection: 'column', gap: '14px'
              }}>
                {/* Header */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <h3 style={{ margin: '0 0 3px', fontSize: '16px', fontWeight: 700, color: '#ec4899', lineHeight: 1.3 }}>
                      {cls.subject_name}
                    </h3>
                    <span style={{
                      fontSize: '10px', fontWeight: 700, background: 'rgba(236,72,153,0.12)',
                      color: '#ec4899', padding: '2px 8px', borderRadius: '20px', whiteSpace: 'nowrap', marginLeft: '8px'
                    }}>{cls.subject_code}</span>
                  </div>
                  {(cls.course_name || cls.semester_name || cls.session_name) && (
                    <div style={{ fontSize: '12px', color: 'var(--gray)', marginTop: '2px' }}>
                      {[cls.session_name, cls.course_name, cls.semester_name].filter(Boolean).join(' · ')}
                    </div>
                  )}
                </div>

                {/* Details */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Clock size={13} style={{ color: '#ec4899', flexShrink: 0 }} />
                    <span>{cls.period_label} &nbsp;·&nbsp; {cls.start_time} – {cls.end_time}</span>
                  </div>
                  {cls.room_name && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <MapPin size={13} style={{ color: '#ec4899', flexShrink: 0 }} />
                      <span>{cls.room_name}{cls.room_building ? `, ${cls.room_building}` : ''}</span>
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <Calendar size={13} style={{ color: '#ec4899', flexShrink: 0 }} />
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {cls.days.map((d: number) => (
                        <span key={d} style={{
                          fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px',
                          background: d === todayIdx ? '#ec4899' : 'rgba(236,72,153,0.12)',
                          color: d === todayIdx ? '#fff' : 'var(--gray)'
                        }}>{dayShort[d]}</span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Action */}
                <button
                  onClick={() => handleTakeAttendance(cls.subject_id, cls.session_id, cls.period_id)}
                  style={{
                    padding: '9px 16px', borderRadius: '10px', fontSize: '13px', fontWeight: 600,
                    border: '1px solid #ec4899', background: 'rgba(236,72,153,0.08)',
                    color: '#ec4899', cursor: 'pointer', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', gap: '7px', width: '100%', transition: 'all 0.15s'
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#ec4899'; (e.currentTarget as HTMLButtonElement).style.color = '#fff'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(236,72,153,0.08)'; (e.currentTarget as HTMLButtonElement).style.color = '#ec4899'; }}
                >
                  <ClipboardCheck size={15} /> Take Attendance
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Today's Classes */}
      <div style={{ marginBottom: '30px' }}>
        <h2 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Calendar size={22} style={{ color: 'var(--primary)' }} />
          Today's Classes
          <span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--gray)' }}>— {daysLabels[todayIdx]}</span>
        </h2>

        {todayClasses.length === 0 ? (
          <div className="glass-card" style={{ padding: '40px', textAlign: 'center' }}>
            <Calendar size={40} style={{ color: 'var(--gray)', opacity: 0.4, marginBottom: '12px' }} />
            <h3 style={{ color: 'var(--gray)', fontWeight: 500, margin: '0 0 4px' }}>No classes scheduled today</h3>
            <p style={{ color: 'var(--gray)', fontSize: '14px', margin: 0 }}>Enjoy your free day!</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '16px' }}>
            {todayClasses.map((cls, i) => (
              <div key={i} className="glass-card" style={{ padding: '24px', borderLeft: '4px solid var(--primary)', position: 'relative', overflow: 'hidden' }}>
                <div style={{ position: 'absolute', top: '12px', right: '16px', fontSize: '11px', color: 'var(--gray)', fontWeight: 500 }}>
                  {cls.period_label}
                </div>
                <h3 style={{ margin: '0 0 6px', fontSize: '18px', color: 'var(--primary)' }}>{cls.subject_name}</h3>
                <div style={{ fontSize: '13px', color: 'var(--gray)', marginBottom: '4px' }}>{cls.subject_code}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginTop: '14px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <Clock size={14} /> {cls.start_time} - {cls.end_time}
                  </span>
                  {cls.room_name && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <MapPin size={14} /> {cls.room_name}{cls.room_building ? `, ${cls.room_building}` : ''}
                    </span>
                  )}
                  {cls.course_name && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <BookOpen size={14} /> {cls.course_name}
                    </span>
                  )}
                  {cls.semester_name && (
                    <span style={{ fontSize: '12px', color: 'var(--gray)' }}>
                      {cls.semester_name}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => handleTakeAttendance(cls.subject_id, cls.session_id, cls.period_id)}
                  className="btn-primary"
                  style={{ marginTop: '18px', padding: '8px 20px', fontSize: '13px', width: '100%' }}
                >
                  <ClipboardCheck size={16} /> Take Attendance
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Full Weekly Schedule */}
      <div>
        <h2 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Clock size={22} style={{ color: 'var(--primary)' }} />
          Weekly Schedule
        </h2>

        {schedule.length === 0 ? (
          <div className="glass-card" style={{ padding: '30px', textAlign: 'center', color: 'var(--gray)' }}>
            No classes assigned to your schedule yet.
          </div>
        ) : (
          <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Day</th>
                  <th>Period / Time</th>
                  <th>Subject</th>
                  <th>Room</th>
                  <th>Course</th>
                  <th style={{ width: '140px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {daysLabels.map((dayLabel, dayIdx) => {
                  const dayClasses = schedule.filter(s => s.day_of_week === dayIdx);
                  if (dayClasses.length === 0) return null;
                  return dayClasses.map((cls, i) => (
                    <tr key={`${dayIdx}-${i}`} style={dayIdx === todayIdx ? { background: 'rgba(99, 102, 241, 0.04)' } : {}}>
                      {i === 0 ? (
                        <td rowSpan={dayClasses.length} style={{ fontWeight: 700, verticalAlign: 'top', borderRight: '2px solid var(--glass-border)', color: dayIdx === todayIdx ? 'var(--primary)' : 'inherit' }}>
                          {dayLabel}
                          {dayIdx === todayIdx && <div style={{ fontSize: '10px', color: 'var(--primary)', fontWeight: 600, marginTop: '4px' }}>TODAY</div>}
                        </td>
                      ) : null}
                      <td>
                        <div style={{ fontWeight: 500 }}>{cls.period_label}</div>
                        <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{cls.start_time} - {cls.end_time}</div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{cls.subject_name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{cls.subject_code}</div>
                      </td>
                      <td>
                        {cls.room_name ? (
                          <div>
                            <div>{cls.room_name}</div>
                            <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{cls.room_building || ''}</div>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--gray)', fontSize: '13px' }}>—</span>
                        )}
                      </td>
                      <td>
                        <div style={{ fontSize: '13px' }}>{cls.course_name || '—'}</div>
                        {cls.semester_name && <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{cls.semester_name}</div>}
                      </td>
                      <td>
                        <button
                          onClick={() => handleTakeAttendance(cls.subject_id, cls.session_id, cls.period_id)}
                          style={{
                            padding: '5px 12px', borderRadius: '8px', fontSize: '12px', fontWeight: 600,
                            border: '1px solid rgba(99, 102, 241, 0.2)', background: 'rgba(99, 102, 241, 0.06)',
                            color: 'var(--primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px',
                            transition: 'all 0.2s ease'
                          }}
                        >
                          <ClipboardCheck size={13} /> Attendance
                        </button>
                      </td>
                    </tr>
                  ));
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

const AttendanceMarking = () => {
  const location = useLocation();
  const qp = new URLSearchParams(location.search);

  const [assignedClasses, setAssignedClasses] = useState<any[]>([]);
  const [allStudents, setAllStudents] = useState<any[]>([]);
  
  const [roster, setRoster] = useState<any[]>([]);
  const [marks, setMarks] = useState<any>({}); // student_id: status
  
  const [selectedClassKey, setSelectedClassKey] = useState('');
  const [selectedSubject, setSelectedSubject] = useState(qp.get('subject') || '');
  const [selectedPeriod, setSelectedPeriod] = useState(qp.get('period') || '');
  
  const [activeTab, setActiveTab] = useState<'attendance'|'roster'>('attendance');
  const [studentToAdd, setStudentToAdd] = useState('');
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [qrToken, setQrToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      const token = localStorage.getItem('token');
      const h = { headers: { Authorization: `Bearer ${token}` } };
      const [schedRes, studentsRes] = await Promise.all([
        axios.get('http://localhost:8080/teacher/schedule', h),
        axios.get('http://localhost:8080/students', h)
      ]);
      
      const uniqueClassMap = new Map<string, any>();
      schedRes.data.forEach((cls: any) => {
        const key = `${cls.subject_id}__${cls.session_id}__${cls.period_id}`;
        if (!uniqueClassMap.has(key)) {
          uniqueClassMap.set(key, { ...cls, days: [] });
        }
        uniqueClassMap.get(key)!.days.push(cls.day_of_week);
      });
      const classes = Array.from(uniqueClassMap.values());
      setAssignedClasses(classes);
      setAllStudents(studentsRes.data);

      const qpSubject = qp.get('subject');
      const qpSession = qp.get('session');
      const qpPeriod = qp.get('period');
      if (qpSubject && qpPeriod) {
        const key = `${qpSubject}__${qpSession || ''}__${qpPeriod}`;
        const match = classes.find((c: any) => `${c.subject_id}__${c.session_id || ''}__${c.period_id}` === key);
        if (match) setSelectedClassKey(key);
      }
    };
    load();
  }, []);

  const fetchRoster = async (subjectId: string) => {
    const token = localStorage.getItem('token');
    const res = await axios.get(`http://localhost:8080/teacher/roster/${subjectId}`, { headers: { Authorization: `Bearer ${token}` } });
    setRoster(res.data);
    const initialMarks: any = {};
    res.data.forEach((s: any) => initialMarks[s.id] = 'present');
    setMarks(initialMarks);
  };

  useEffect(() => {
    if (selectedClassKey) {
      const [subj, , per] = selectedClassKey.split('__');
      setSelectedSubject(subj);
      setSelectedPeriod(per);
      fetchRoster(subj);
    } else {
      setSelectedSubject('');
      setSelectedPeriod('');
      setRoster([]);
    }
  }, [selectedClassKey]);

  const handleSave = async () => {
    if (!selectedSubject || !selectedPeriod) return alert("Select subject and period");
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      // The backend expects single records at /attendance/mark
      const requests = Object.keys(marks).map(sid => 
        axios.post('http://localhost:8080/attendance/mark', {
          student_id: parseInt(sid),
          subject_id: parseInt(selectedSubject),
          period_id: parseInt(selectedPeriod),
          date: selectedDate, // note: backend currently forces today's date if 'date' is ignored, but we pass it anyway
          status: marks[sid]
        }, { headers: { Authorization: `Bearer ${token}` } })
      );
      await Promise.all(requests);
      alert("Attendance saved successfully");
    } catch (e) { alert("Error saving attendance"); }
    finally { setLoading(false); }
  };

  const handleAddStudent = async () => {
    if (!selectedSubject || !studentToAdd) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`http://localhost:8080/teacher/roster/${selectedSubject}/${studentToAdd}`, {}, { headers: { Authorization: `Bearer ${token}` } });
      setStudentToAdd('');
      fetchRoster(selectedSubject);
    } catch (e: any) {
      alert(e.response?.data?.detail || "Error adding student");
    } finally { setLoading(false); }
  };

  const handleRemoveStudent = async (studentId: number) => {
    if (!selectedSubject || !window.confirm("Remove this student from the class?")) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`http://localhost:8080/teacher/roster/${selectedSubject}/${studentId}`, { headers: { Authorization: `Bearer ${token}` } });
      fetchRoster(selectedSubject);
    } catch (e: any) {
      alert(e.response?.data?.detail || "Error removing student");
    } finally { setLoading(false); }
  };

  const handleGenerateClassQR = async () => {
    if (!selectedClassKey) return alert("Select an assigned class first.");
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post('http://localhost:8080/teacher/generate_qr', {
        subject_id: parseInt(selectedSubject),
        period_id: parseInt(selectedPeriod)
      }, { headers: { Authorization: `Bearer ${token}` } });
      setQrToken(res.data.token);
    } catch (e: any) {
      alert("Error generating QR code.");
    } finally { setLoading(false); }
  };

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1>Day / Period wise Attendance</h1>
        <button onClick={qrToken ? () => setQrToken(null) : handleGenerateClassQR} className="btn-ghost" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Smartphone size={18} /> {qrToken ? 'Hide QR Code' : 'Display Class QR'}
        </button>
      </div>

      <div className="glass-card" style={{ padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '20px', marginBottom: '20px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>SELECT CLASS</label>
            <select value={selectedClassKey} onChange={e => setSelectedClassKey(e.target.value)} style={{ padding: '12px' }}>
              <option value="">Select an assigned class...</option>
              {assignedClasses.map(c => {
                const key = `${c.subject_id}__${c.session_id}__${c.period_id}`;
                const days = c.days.map((d: number) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d]).join(', ');
                return (
                  <option key={key} value={key}>
                    {c.subject_name} {c.session_name ? `(${c.session_name})` : ''} - {c.period_label} ({days})
                  </option>
                );
              })}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>DATE</label>
            <input type="date" value={selectedDate} onChange={e => setSelectedDate(e.target.value)} style={{ padding: '11px' }} />
          </div>
        </div>

        {qrToken && (
          <div style={{ textAlign: 'center', margin: '0 auto 30px', padding: '30px', borderRadius: '12px', background: 'rgba(99, 102, 241, 0.05)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
            <h2 style={{ color: 'var(--primary)', marginBottom: '10px' }}>Class Session Active</h2>
            <p style={{ color: 'var(--gray)', marginBottom: '20px' }}>Students can scan this QR code from their portal to mark presence.</p>
            <div style={{ background: 'white', padding: '20px', borderRadius: '10px', display: 'inline-block' }}>
              <QRCodeSVG value={qrToken} size={250} level="M" />
            </div>
          </div>
        )}

        {selectedSubject && (
          <div style={{ marginTop: '30px' }}>
            <div style={{ display: 'flex', gap: '15px', marginBottom: '20px', borderBottom: '1px solid var(--glass-border)', paddingBottom: '15px' }}>
              <button 
                onClick={() => setActiveTab('attendance')} 
                className={activeTab === 'attendance' ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '8px 20px', borderRadius: '10px' }}
              >Take Attendance</button>
              <button 
                onClick={() => setActiveTab('roster')} 
                className={activeTab === 'roster' ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '8px 20px', borderRadius: '10px' }}
              >Manage Roster</button>
            </div>

            {activeTab === 'roster' && (
              <div style={{ marginBottom: '20px', padding: '15px', border: '1px dashed var(--glass-border)', borderRadius: '12px', display: 'flex', gap: '10px' }}>
                <select value={studentToAdd} onChange={e => setStudentToAdd(e.target.value)} style={{ flex: 1 }}>
                  <option value="">-- Select Student to Enroll --</option>
                  {allStudents.filter(st => !roster.find(r => r.id === st.id)).map(st => (
                    <option key={st.id} value={st.id}>{st.student_code} - {st.full_name}</option>
                  ))}
                </select>
                <button onClick={handleAddStudent} disabled={loading || !studentToAdd} className="btn-primary" style={{ padding: '0 20px', whiteSpace: 'nowrap' }}>
                  <Users size={16} style={{ marginRight: '8px' }} /> Enroll Student
                </button>
              </div>
            )}

            <div style={{ overflow: 'hidden', borderRadius: '12px', border: '1px solid var(--glass-border)' }}>
              <table className="data-table" style={{ width: '100%' }}>
                <thead style={{ background: 'var(--table-header-bg)' }}>
                  <tr>
                    <th style={{ padding: '15px' }}>Student</th>
                    <th>ID Code</th>
                    <th style={{ width: activeTab === 'attendance' ? 'auto' : '100px' }}>
                      {activeTab === 'attendance' ? 'Attendance Status' : 'Actions'}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {roster.length === 0 ? (
                    <tr><td colSpan={3} style={{ textAlign: 'center', padding: '30px', color: 'var(--gray)' }}>No students enrolled.</td></tr>
                  ) : roster.map(st => (
                    <tr key={st.id}>
                      <td style={{ fontWeight: 500, padding: '12px 15px' }}>{st.full_name}</td>
                      <td style={{ color: 'var(--gray)', fontSize: '13px' }}>{st.student_code}</td>
                      <td>
                        {activeTab === 'attendance' ? (
                          <div style={{ display: 'flex', gap: '5px' }}>
                            {['present', 'absent', 'late', 'excused'].map(stat => (
                              <button key={stat}
                                onClick={() => setMarks({ ...marks, [st.id]: stat })}
                                className={marks[st.id] === stat ? 'btn-primary' : 'btn-ghost'}
                                style={{
                                  padding: '4px 10px', fontSize: '11px', borderRadius: '8px', textTransform: 'capitalize',
                                  background: marks[st.id] === stat ? (stat === 'absent' ? '#ef4444' : stat === 'late' ? '#f59e0b' : 'var(--primary)') : 'transparent'
                                }}>
                                {stat}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <button onClick={() => handleRemoveStudent(st.id)} disabled={loading} style={{ color: '#ef4444', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold' }}>
                            Remove
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {activeTab === 'attendance' && roster.length > 0 && (
                <div style={{ padding: '20px', background: 'var(--table-header-bg)', display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--glass-border)' }}>
                  <button onClick={handleSave} disabled={loading} className="btn-primary" style={{ padding: '10px 30px' }}>
                    {loading ? 'Saving...' : 'Confirm & Save Attendance'}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const AdminAttendance = () => {
  const [records, setRecords] = useState<any[]>([]);
  const [students, setStudents] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [periods, setPeriods] = useState<any[]>([]);
  const [teachers, setTeachers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editStatus, setEditStatus] = useState('');

  const [filters, setFilters] = useState<any>({
    student_id: '', subject_id: '', period_id: '',
    date_from: '', date_to: '', status: ''
  });

  const [formData, setFormData] = useState<any>({
    student_user_id: '', subject_id: '', period_id: '',
    teacher_user_id: '', attendance_date: adToBs(new Date().toISOString().split('T')[0]),
    status: 'present'
  });

  const token = localStorage.getItem('token');
  const h = { headers: { Authorization: `Bearer ${token}` } };

  const fetchLookups = async () => {
    const [stuRes, subRes, perRes, teaRes] = await Promise.all([
      axios.get('http://localhost:8080/students', h),
      axios.get('http://localhost:8080/academic/subjects', h),
      axios.get('http://localhost:8080/academic/periods', h),
      axios.get('http://localhost:8080/admin/users/all', h)
    ]);
    setStudents(stuRes.data);
    setSubjects(subRes.data);
    setPeriods(perRes.data);
    setTeachers(teaRes.data.filter((u: any) => u.role === 'teacher'));
  };

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.student_id) params.append('student_id', filters.student_id);
      if (filters.subject_id) params.append('subject_id', filters.subject_id);
      if (filters.period_id) params.append('period_id', filters.period_id);
      if (filters.date_from) params.append('date_from', bsToAd(filters.date_from));
      if (filters.date_to) params.append('date_to', bsToAd(filters.date_to));
      if (filters.status) params.append('status', filters.status);
      const res = await axios.get(`http://localhost:8080/admin/attendance?${params.toString()}`, h);
      setRecords(res.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchLookups(); }, []);
  useEffect(() => { fetchRecords(); }, [filters]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const adFormData = { ...formData, attendance_date: bsToAd(formData.attendance_date) };
      await axios.post('http://localhost:8080/admin/attendance', adFormData, h);
      setFormData({ ...formData, student_user_id: '', status: 'present' });
      setShowForm(false);
      fetchRecords();
    } catch (e: any) { alert(e.response?.data?.detail || "Error adding record. Check BS date format."); }
  };

  const handleEdit = (rec: any) => {
    setEditingId(rec.id);
    setEditStatus(rec.status);
  };

  const handleSaveEdit = async (id: number) => {
    try {
      await axios.put(`http://localhost:8080/admin/attendance/${id}`, { status: editStatus }, h);
      setEditingId(null);
      fetchRecords();
    } catch (e) { alert("Error updating record"); }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this attendance record?")) return;
    try {
      await axios.delete(`http://localhost:8080/admin/attendance/${id}`, h);
      fetchRecords();
    } catch (e) { alert("Error deleting record"); }
  };

  const resetFilters = () => setFilters({ student_id: '', subject_id: '', period_id: '', date_from: '', date_to: '', status: '' });

  const handleExportPDF = () => {
    if (records.length === 0) return alert('No records to export. Adjust your filters.');

    // Build filter description
    const filterParts: string[] = [];
    if (filters.student_id) { const s = students.find((x: any) => String(x.id) === String(filters.student_id)); if (s) filterParts.push(`Student: ${s.full_name}`); }
    if (filters.subject_id) { const s = subjects.find((x: any) => String(x.id) === String(filters.subject_id)); if (s) filterParts.push(`Subject: ${s.code} — ${s.name}`); }
    if (filters.period_id) { const p = periods.find((x: any) => String(x.id) === String(filters.period_id)); if (p) filterParts.push(`Period: ${p.label}`); }
    if (filters.status) filterParts.push(`Status: ${filters.status}`);
    if (filters.date_from) filterParts.push(`From: ${filters.date_from}`);
    if (filters.date_to) filterParts.push(`To: ${filters.date_to}`);
    const filterLine = filterParts.length > 0
      ? `<p style="color:#64748b;font-size:12px;margin:4px 0 16px;">Filters: ${filterParts.join(' &bull; ')}</p>`
      : '<p style="color:#64748b;font-size:12px;margin:4px 0 16px;">Showing all records (no filters applied)</p>';

    const statusBadge = (s: string) => {
      const colors: any = { present: '#059669', absent: '#dc2626', late: '#d97706', excused: '#7c3aed' };
      const bgs: any = { present: '#ecfdf5', absent: '#fef2f2', late: '#fffbeb', excused: '#f5f3ff' };
      return `<span style="padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;background:${bgs[s] || '#f1f5f9'};color:${colors[s] || '#475569'};text-transform:capitalize;">${s}</span>`;
    };

    let rows = '';
    for (const rec of records) {
      rows += `<tr>
        <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-weight:600;white-space:nowrap;">${adToBs(rec.attendance_date)}</td>
        <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;">
          <div style="font-weight:500;">${rec.student_name}</div>
          <div style="font-size:10px;color:#94a3b8;">${rec.student_code || ''}</div>
        </td>
        <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;">
          <div style="font-weight:500;">${rec.subject_name}</div>
          <div style="font-size:10px;color:#94a3b8;">${rec.subject_code}</div>
        </td>
        <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;">
          <div>${rec.period_label}</div>
          <div style="font-size:10px;color:#94a3b8;">${rec.start_time}-${rec.end_time}</div>
        </td>
        <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;">${rec.teacher_name}</td>
        <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;">${statusBadge(rec.status)}</td>
        <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:11px;color:#94a3b8;text-transform:capitalize;">${(rec.capture_method || '').replace(/_/g, ' ')}</td>
      </tr>`;
    }

    const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Attendance Report</title>
<style>
  @page { size: landscape; margin: 12mm; }
  body { font-family: 'Inter', -apple-system, sans-serif; color: #1e293b; margin: 0; padding: 24px; }
  table { width: 100%; border-collapse: collapse; }
  @media print { body { padding: 0; } }
</style></head><body>
  <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:4px;">
    <h2 style="margin:0;font-size:20px;">Day / Period wise Attendance Report</h2>
    <div style="font-size:11px;color:#94a3b8;">${new Date().toLocaleString()}</div>
  </div>
  ${filterLine}
  <div style="display:flex;gap:20px;margin-bottom:16px;font-size:12px;font-weight:600;">
    <span>Total: <strong>${total}</strong></span>
    <span style="color:#059669;">Present: ${presentCount}</span>
    <span style="color:#dc2626;">Absent: ${absentCount}</span>
    <span style="color:#d97706;">Late: ${lateCount}</span>
    <span style="color:#7c3aed;">Excused: ${excusedCount}</span>
  </div>
  <table>
    <thead>
      <tr>
        <th style="padding:10px 14px;text-align:left;background:#6366f1;color:white;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Date</th>
        <th style="padding:10px 14px;text-align:left;background:#6366f1;color:white;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Student</th>
        <th style="padding:10px 14px;text-align:left;background:#6366f1;color:white;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Subject</th>
        <th style="padding:10px 14px;text-align:left;background:#6366f1;color:white;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Period</th>
        <th style="padding:10px 14px;text-align:left;background:#6366f1;color:white;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Teacher</th>
        <th style="padding:10px 14px;text-align:left;background:#6366f1;color:white;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Status</th>
        <th style="padding:10px 14px;text-align:left;background:#6366f1;color:white;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Method</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>
  <p style="margin-top:20px;font-size:10px;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:10px;">Generated from Attendance Portal &bull; ${records.length} record(s)</p>
</body></html>`;

    const win = window.open('', '_blank');
    if (win) {
      win.document.write(html);
      win.document.close();
      setTimeout(() => win.print(), 300);
    }
  };

  // Stats
  const total = records.length;
  const presentCount = records.filter(r => r.status === 'present').length;
  const absentCount = records.filter(r => r.status === 'absent').length;
  const lateCount = records.filter(r => r.status === 'late').length;
  const excusedCount = records.filter(r => r.status === 'excused').length;

  const statusColor = (s: string) => {
    if (s === 'present') return '#10b981';
    if (s === 'absent') return '#ef4444';
    if (s === 'late') return '#f59e0b';
    return '#6366f1';
  };

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ marginBottom: '4px' }}>Day / Period wise Attendance</h1>
          <p style={{ color: 'var(--gray)', fontSize: '14px', margin: 0 }}>Manage all attendance records across students, subjects, and periods</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={handleExportPDF} className="btn-secondary" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Download size={18} /> Export PDF
          </button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary" style={{ padding: '10px 20px' }}>
            <Plus size={18} /> {showForm ? 'Close Form' : 'Add Record'}
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      {total > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '24px' }}>
          {[
            { label: 'Total Records', val: total, color: '#6366f1' },
            { label: 'Present', val: presentCount, color: '#10b981' },
            { label: 'Absent', val: absentCount, color: '#ef4444' },
            { label: 'Late', val: lateCount, color: '#f59e0b' },
            { label: 'Excused', val: excusedCount, color: '#8b5cf6' }
          ].map((s, i) => (
            <div key={i} className="glass-card" style={{ padding: '16px 20px', borderLeft: `4px solid ${s.color}`, cursor: 'default' }}>
              <div style={{ fontSize: '12px', color: 'var(--gray)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
              <div style={{ fontSize: '28px', fontWeight: 700, marginTop: '4px' }}>{s.val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Add Record Form */}
      {showForm && (
        <div className="glass-card" style={{ padding: '24px', marginBottom: '24px', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
          <h3 style={{ margin: '0 0 16px', color: 'var(--primary)' }}>Add Attendance Record</h3>
          <form onSubmit={handleAdd} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '15px', alignItems: 'flex-end' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>STUDENT</label>
              <select value={formData.student_user_id} onChange={e => setFormData({ ...formData, student_user_id: parseInt(e.target.value) })} required>
                <option value="">Select Student</option>
                {students.map((s: any) => <option key={s.id} value={s.id}>{s.full_name} ({s.student_code})</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>SUBJECT</label>
              <select value={formData.subject_id} onChange={e => setFormData({ ...formData, subject_id: parseInt(e.target.value) })} required>
                <option value="">Select Subject</option>
                {subjects.map((s: any) => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>PERIOD</label>
              <select value={formData.period_id} onChange={e => setFormData({ ...formData, period_id: parseInt(e.target.value) })} required>
                <option value="">Select Period</option>
                {periods.map((p: any) => <option key={p.id} value={p.id}>{p.label} ({p.start_time}-{p.end_time})</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>TEACHER</label>
              <select value={formData.teacher_user_id} onChange={e => setFormData({ ...formData, teacher_user_id: parseInt(e.target.value) })} required>
                <option value="">Select Teacher</option>
                {teachers.map((t: any) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>DATE</label>
              <input type="date" value={formData.attendance_date} onChange={e => setFormData({ ...formData, attendance_date: e.target.value })} required />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>STATUS</label>
              <select value={formData.status} onChange={e => setFormData({ ...formData, status: e.target.value })}>
                <option value="present">Present</option>
                <option value="absent">Absent</option>
                <option value="late">Late</option>
                <option value="excused">Excused</option>
              </select>
            </div>
            <button type="submit" className="btn-primary" style={{ height: '45px' }}>
              <Save size={18} /> Save Record
            </button>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="glass-card" style={{ padding: '24px', marginBottom: '24px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '20px', position: 'relative', zIndex: 50 }}>
        <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
          <Filter size={20} color="var(--primary)" />
          <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text)' }}>Filter Attendance Records:</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Student</label>
          <select style={{ width: '100%' }} value={filters.student_id} onChange={e => setFilters({ ...filters, student_id: e.target.value })}>
            <option value="">All Students</option>
            {students.map((s: any) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Subject</label>
          <select style={{ width: '100%' }} value={filters.subject_id} onChange={e => setFilters({ ...filters, subject_id: e.target.value })}>
            <option value="">All Subjects</option>
            {subjects.map((s: any) => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Period</label>
          <select style={{ width: '100%' }} value={filters.period_id} onChange={e => setFilters({ ...filters, period_id: e.target.value })}>
            <option value="">All Periods</option>
            {periods.map((p: any) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status</label>
          <select style={{ width: '100%' }} value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}>
            <option value="">All Status</option>
            <option value="present">Present</option>
            <option value="absent">Absent</option>
            <option value="late">Late</option>
            <option value="excused">Excused</option>
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>From (BS)</label>
          <NepaliDatePicker value={filters.date_from} onChange={v => setFilters({ ...filters, date_from: v })} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>To (BS)</label>
          <NepaliDatePicker value={filters.date_to} onChange={v => setFilters({ ...filters, date_to: v })} />
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button onClick={resetFilters} className="btn-ghost" style={{ width: '100%', height: '42px', justifySelf: 'end' }}>Reset Filters</button>
        </div>
      </div>

      {/* Records Table */}
      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--gray)' }}>Loading records...</div>
        ) : records.length === 0 ? (
          <div style={{ padding: '60px 40px', textAlign: 'center' }}>
            <ClipboardCheck size={48} style={{ color: 'var(--gray)', marginBottom: '16px', opacity: 0.4 }} />
            <h3 style={{ color: 'var(--gray)', fontWeight: 500 }}>No attendance records found</h3>
            <p style={{ color: 'var(--gray)', fontSize: '14px' }}>Adjust filters or add a new record to get started.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Student</th>
                <th>Subject</th>
                <th>Period</th>
                <th>Teacher</th>
                <th>Status</th>
                <th>Method</th>
                <th style={{ width: '100px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.map(rec => (
                <tr key={rec.id}>
                  <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{adToBs(rec.attendance_date)}</td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{rec.student_name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{rec.student_code}</div>
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{rec.subject_name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{rec.subject_code}</div>
                  </td>
                  <td>
                    <div>{rec.period_label}</div>
                    <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{rec.start_time}-{rec.end_time}</div>
                  </td>
                  <td>{rec.teacher_name}</td>
                  <td>
                    {editingId === rec.id ? (
                      <select value={editStatus} onChange={e => setEditStatus(e.target.value)} style={{ width: '100px', padding: '4px 8px', fontSize: '13px' }}>
                        <option value="present">Present</option>
                        <option value="absent">Absent</option>
                        <option value="late">Late</option>
                        <option value="excused">Excused</option>
                      </select>
                    ) : (
                      <span style={{
                        padding: '4px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 600,
                        background: `${statusColor(rec.status)}18`, color: statusColor(rec.status),
                        textTransform: 'capitalize'
                      }}>
                        {rec.status}
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: '11px', color: 'var(--gray)', textTransform: 'capitalize' }}>{rec.capture_method?.replace(/_/g, ' ')}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {editingId === rec.id ? (
                        <>
                          <button onClick={() => handleSaveEdit(rec.id)} style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: 'none', cursor: 'pointer', fontSize: '12px' }}>Save</button>
                          <button onClick={() => setEditingId(null)} style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(100, 116, 139, 0.1)', color: '#64748b', border: 'none', cursor: 'pointer', fontSize: '12px' }}>Cancel</button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => handleEdit(rec)} style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', border: 'none', cursor: 'pointer', fontSize: '12px' }} title="Edit status">
                            <Edit2 size={14} />
                          </button>
                          <button onClick={() => handleDelete(rec.id)} style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: 'none', cursor: 'pointer', fontSize: '12px' }} title="Delete record">
                            <Trash2 size={14} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

const ComplianceExport = () => {
  const todayBS = adToBs(new Date().toISOString().split('T')[0]);
  const [start, setStart] = useState(todayBS.slice(0, 8) + "01"); // Start of BS month
  const [end, setEnd] = useState(todayBS);
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const adStart = bsToAd(start);
      const adEnd = bsToAd(end);
      const res = await axios.get(`http://localhost:8080/export/compliance?start_date=${adStart}&end_date=${adEnd}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const blob = new Blob([res.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compliance_report_${start}_to_${end}.csv`;
      a.click();
    } finally { setLoading(false); }
  };

  return (
    <div className="fade-in">
      <h1>Compliance Reports</h1>
      <p style={{ color: 'var(--gray)', marginBottom: '30px' }}>Generate official CSV records for auditing.</p>

      <div className="glass-card" style={{ padding: '30px', maxWidth: '600px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'flex', gap: '15px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>Start Date (BS)</label>
              <NepaliDatePicker value={start} onChange={setStart} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>End Date (BS)</label>
              <NepaliDatePicker value={end} onChange={setEnd} />
            </div>
          </div>
          <button className="btn-primary" onClick={handleExport} disabled={loading}>
            {loading ? 'Generating...' : <><Download size={18} /> Export Compliance CSV</>}
          </button>
        </div>
      </div>
    </div>
  );
};

const StudentReports = () => {
  const [summary, setSummary] = useState<any[]>([]);
  const [monthly, setMonthly] = useState<any[]>([]);

  useEffect(() => {
    const fetch = async () => {
      try {
        const token = localStorage.getItem('token');
        const h = { headers: { Authorization: `Bearer ${token}` } };
        const [sumRes, monRes] = await Promise.all([
          axios.get('http://localhost:8080/attendance/summary', h),
          axios.get('http://localhost:8080/attendance/student_stats_bs', h)
        ]);
        setSummary(sumRes.data);
        setMonthly(monRes.data);
      } catch (e) { console.error(e); }
    };
    fetch();
  }, []);

  const getMonthName = (m: number) => [
    "Baisakh", "Jestha", "Ashad", "Shrawan", "Bhadra", "Ashwin",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
  ][m - 1];

  return (
    <div className="fade-in">
      <h1>My Attendance Reports</h1>
      <p style={{ color: 'var(--gray)', marginBottom: '30px' }}>Comprehensive analysis of your attendance based on the Nepali calendar.</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px', marginBottom: '40px' }}>
        {summary.map((r, i) => (
          <div key={i} className="glass-card" style={{ padding: '24px', borderTop: `4px solid ${r.status === 'present' ? '#10b981' : '#ef4444'}` }}>
            <h3 style={{ textTransform: 'capitalize', fontSize: '14px', color: 'var(--gray)' }}>Total {r.status}</h3>
            <div style={{ fontSize: '36px', fontWeight: 'bold', margin: '8px 0' }}>{r.count}</div>
          </div>
        ))}
      </div>

      <h2 style={{ marginBottom: '20px' }}>Monthly Breakdown (BS)</h2>
      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Nepali Month</th>
              <th>Present</th>
              <th>Absent</th>
              <th>Late</th>
              <th>Excused</th>
              <th>Total Cycles</th>
              <th>Attendance %</th>
            </tr>
          </thead>
          <tbody>
            {monthly.map((m, i) => {
              const attendancePct = m.total > 0 ? Math.round(((m.present + m.late + m.excused) / m.total) * 100) : 0;
              return (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{getMonthName(m.month)} {m.year}</td>
                  <td style={{ color: '#10b981' }}>{m.present}</td>
                  <td style={{ color: '#ef4444' }}>{m.absent}</td>
                  <td style={{ color: '#f59e0b' }}>{m.late}</td>
                  <td style={{ color: '#8b5cf6' }}>{m.excused}</td>
                  <td>{m.total}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ flex: 1, background: '#f1f5f9', height: '6px', borderRadius: '3px', overflow: 'hidden', minWidth: '60px' }}>
                        <div style={{ width: `${attendancePct}%`, height: '100%', background: attendancePct > 80 ? '#10b981' : attendancePct > 60 ? '#f59e0b' : '#ef4444' }}></div>
                      </div>
                      <span style={{ fontWeight: 700, fontSize: '13px' }}>{attendancePct}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
            {monthly.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--gray)' }}>No monthly data available yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};


const EntityManager = ({ title, endpoint, columns, fields }: { title: string, endpoint: string, columns: string[], fields: any[] }) => {
  const [data, setData] = useState<any[]>([]);
  const [formData, setFormData] = useState<any>({});
  const [editingId, setEditingId] = useState<number | null>(null);

  const fetchItems = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`http://localhost:8080/academic/${endpoint}`, { headers: { Authorization: `Bearer ${token}` } });
      setData(res.data);
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    setFormData({});
    setEditingId(null);
    fetchItems();
  }, [endpoint]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('token');
      // Convert dates from BS to AD if necessary
      const processedData = { ...formData };
      fields.forEach(f => {
        if (f.isDate && processedData[f.name]) {
          processedData[f.name] = bsToAd(processedData[f.name]);
        }
      });

      if (editingId) {
        await axios.put(`http://localhost:8080/academic/${endpoint}/${editingId}`, processedData, { headers: { Authorization: `Bearer ${token}` } });
      } else {
        await axios.post(`http://localhost:8080/academic/${endpoint}`, processedData, { headers: { Authorization: `Bearer ${token}` } });
      }
      setFormData({});
      setEditingId(null);
      fetchItems();
    } catch (e) { alert("Error saving item. Check date formats (BS: YYYY-MM-DD)"); }
  };

  const handleEdit = (item: any) => {
    setEditingId(item.id);
    const bsFormData = { ...item };
    fields.forEach(f => {
      if (f.isDate && bsFormData[f.name]) bsFormData[f.name] = adToBs(bsFormData[f.name]);
    });
    setFormData(bsFormData);
  };

  const handleDelete = async (id: number) => {
    if (!confirm(`Delete this ${title.slice(0, -1)}?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`http://localhost:8080/academic/${endpoint}/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      fetchItems();
    } catch (e) { alert("Error deleting item"); }
  };

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <h1>{title}</h1>
        {editingId && <button onClick={() => { setEditingId(null); setFormData({}); }} className="btn-secondary">Cancel Edit</button>}
      </div>

      <div className="glass-card" style={{ padding: '24px', marginBottom: '30px' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '15px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          {fields.map(f => (
            <div key={f.name} style={{ flex: 1, minWidth: '200px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--gray)' }}>{f.label}</label>
              {f.isDate ? (
                <NepaliDatePicker 
                  value={formData[f.name] || ''} 
                  onChange={val => setFormData({ ...formData, [f.name]: val })} 
                  placeholder={f.placeholder}
                  required
                />
              ) : (
                <input
                  type={f.type || 'text'}
                  value={formData[f.name] || ''}
                  onChange={e => setFormData({ ...formData, [f.name]: e.target.value })}
                  placeholder={f.placeholder}
                  required
                />
              )}
            </div>
          ))}
          <button type="submit" className="btn-primary" style={{ height: '45px' }}>
            {editingId ? <><ClipboardCheck size={18} /> Update</> : <><Plus size={18} /> Add {title.slice(0, -1)}</>}
          </button>
        </form>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              {columns.map(c => <th key={c}>{c}</th>)}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, i) => (
              <tr key={i}>
                {fields.map(f => <td key={f.name}>{f.isDate ? adToBs(item[f.name]) : item[f.name]}</td>)}
                <td>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={() => handleEdit(item)} style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', border: 'none', cursor: 'pointer' }}>Edit</button>
                    <button onClick={() => handleDelete(item.id)} style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: 'none', cursor: 'pointer' }}>Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const AdminUsers = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [formData, setFormData] = useState({ username: '', password: '', role: 'teacher', full_name: '', email: '' });

  const fetchUsers = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://localhost:8080/admin/users/all', { headers: { Authorization: `Bearer ${token}` } });
      setUsers(res.data);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('token');
      await axios.post('http://localhost:8080/admin/users', formData, { headers: { Authorization: `Bearer ${token}` } });
      setFormData({ username: '', password: '', role: 'teacher', full_name: '', email: '' });
      fetchUsers();
    } catch (e) { alert("Error adding user"); }
  };

  const handleDelete = async (uid: number) => {
    if (!confirm("Delete this user?")) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`http://localhost:8080/admin/users/${uid}`, { headers: { Authorization: `Bearer ${token}` } });
      fetchUsers();
    } catch (e) { alert("Error deleting"); }
  };

  return (
    <div className="fade-in">
      <h1>Users & Roles</h1>
      <div className="glass-card" style={{ padding: '24px', marginBottom: '30px' }}>
        <form onSubmit={handleAdd} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--gray)' }}>Full Name</label>
            <input value={formData.full_name} onChange={e => setFormData({ ...formData, full_name: e.target.value })} placeholder="John Doe" />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--gray)' }}>Username</label>
            <input value={formData.username} onChange={e => setFormData({ ...formData, username: e.target.value })} placeholder="jdoe" />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--gray)' }}>Password</label>
            <input type="password" value={formData.password} onChange={e => setFormData({ ...formData, password: e.target.value })} placeholder="••••" />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '12px', color: 'var(--gray)' }}>Role</label>
            <select value={formData.role} onChange={e => setFormData({ ...formData, role: e.target.value })}>
              <option value="teacher">Teacher</option>
              <option value="student">Student</option>
              <option value="parent">Parent</option>
            </select>
          </div>
          <button type="submit" className="btn-primary" style={{ height: '45px' }}><Plus size={18} /> Create</button>
        </form>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Full Name</th>
              <th>Username</th>
              <th>Role</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}>
                <td>{u.id}</td>
                <td style={{ fontWeight: 600 }}>{u.full_name}</td>
                <td>{u.username}</td>
                <td><span className={`badge badge-${u.role === 'teacher' ? 'present' : u.role === 'student' ? 'late' : 'absent'}`}>{u.role}</span></td>
                <td>
                  <button onClick={() => handleDelete(u.id)} style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: 'none', cursor: 'pointer' }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const AdminTimetable = ({ isArchived = false }: { isArchived?: boolean }) => {
  const [entries, setEntries] = useState<any[]>([]);
  const [formData, setFormData] = useState<any>({ session_id: '', course_id: '', semester_id: '', subject_id: '', teacher_user_id: '', room_id: '', period_id: '', days: [] });
  const [filters, setFilters] = useState<any>({ session_id: '', course_id: '', semester_id: '', teacher_id: '' });
  const [lookups, setLookups] = useState<any>({ sessions: [], courses: [], semesters: [], subjects: [], teachers: [], rooms: [], periods: [] });
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [editingId, setEditingId] = useState<number | null>(null);

  const fetchData = async () => {
    const token = localStorage.getItem('token');
    const h = { headers: { Authorization: `Bearer ${token}` } };
    const params = new URLSearchParams();
    if (filters.session_id) params.append('session_id', filters.session_id);
    if (filters.course_id) params.append('course_id', filters.course_id);
    if (filters.semester_id) params.append('semester_id', filters.semester_id);
    if (filters.teacher_id) params.append('teacher_id', filters.teacher_id);
    params.append('is_archived', isArchived ? '1' : '0');

    const [e, s, c, sem, sub, t, r, p] = await Promise.all([
      axios.get(`http://localhost:8080/admin/timetable/all?${params.toString()}`, h),
      axios.get('http://localhost:8080/academic/sessions', h),
      axios.get('http://localhost:8080/academic/courses', h),
      axios.get('http://localhost:8080/academic/semesters', h),
      axios.get('http://localhost:8080/academic/subjects', h),
      axios.get('http://localhost:8080/admin/users/all', h),
      axios.get('http://localhost:8080/academic/rooms', h),
      axios.get('http://localhost:8080/academic/periods', h)
    ]);
    setEntries(e.data);
    setLookups({
      sessions: s.data, courses: c.data, semesters: sem.data,
      subjects: sub.data, teachers: t.data.filter((u: any) => u.role === 'teacher'),
      rooms: r.data, periods: p.data
    });
  };

  useEffect(() => { fetchData(); }, [filters]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirm(`Are you sure you want to ${editingId ? 'update' : 'add'} this timetable slot?`)) return;
    try {
      const token = localStorage.getItem('token');
      const h = { headers: { Authorization: `Bearer ${token}` } };
      if (editingId) {
        await axios.put(`http://localhost:8080/admin/timetable/${editingId}`, {
          ...formData,
          day_of_week: formData.days[0]
        }, h);
        setEditingId(null);
      } else {
        await axios.post('http://localhost:8080/admin/timetable', formData, h);
      }
      setFormData({ session_id: '', course_id: '', semester_id: '', subject_id: '', teacher_user_id: '', room_id: '', period_id: '', days: [] });
      fetchData();
    } catch (e: any) { alert(e.response?.data?.detail || "Error saving timetable"); }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this entry?")) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`http://localhost:8080/admin/timetable/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchData();
    } catch (e) { alert("Error deleting entry"); }
  };

  const handleEdit = (ent: any) => {
    setEditingId(ent.id);
    setFormData({
      session_id: ent.session_id,
      course_id: ent.course_id,
      semester_id: ent.semester_id,
      subject_id: ent.subject_id,
      teacher_user_id: ent.teacher_user_id,
      room_id: ent.room_id || '',
      period_id: ent.period_id,
      days: [ent.day_of_week]
    });
  };

  const handleArchive = async (id: number) => {
    if (!window.confirm("Are you sure you want to archive this timetable slot? It will be hidden from teachers and students.")) return;
    try {
      const token = localStorage.getItem('token');
      await axios.put(`http://localhost:8080/admin/timetable/${id}/archive`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchData();
    } catch (e) { alert("Error archiving entry"); }
  };

  const handleUnarchive = async (id: number) => {
    if (!window.confirm("Are you sure you want to restore this slot to the Master Schedule?")) return;
    try {
      const token = localStorage.getItem('token');
      await axios.put(`http://localhost:8080/admin/timetable/${id}/unarchive`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchData();
    } catch (e) { alert("Error unarchiving entry"); }
  };

  const handleExport = async () => {
    if (viewMode === 'grid') {
      // Build grid-view HTML client-side
      const daysShort = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      const sortedPeriods = [...lookups.periods].sort((a: any, b: any) => a.sort_order - b.sort_order);

      // Build filter description
      const filterParts: string[] = [];
      if (filters.session_id) { const s = lookups.sessions.find((x: any) => String(x.id) === String(filters.session_id)); if (s) filterParts.push(`Session: ${s.label}`); }
      if (filters.course_id) { const c = lookups.courses.find((x: any) => String(x.id) === String(filters.course_id)); if (c) filterParts.push(`Course: ${c.name}`); }
      if (filters.semester_id) { const s = lookups.semesters.find((x: any) => String(x.id) === String(filters.semester_id)); if (s) filterParts.push(`Semester: ${s.name}`); }
      if (filters.teacher_id) { const t = lookups.teachers.find((x: any) => String(x.id) === String(filters.teacher_id)); if (t) filterParts.push(`Teacher: ${t.full_name}`); }
      const filterLine = filterParts.length > 0 ? `<p style="color:#64748b;font-size:12px;margin:0 0 16px;">${filterParts.join(' &bull; ')}</p>` : '';

      let rows = '';
      for (const p of sortedPeriods) {
        let cells = '';
        for (let d = 0; d < 7; d++) {
          const dayEntries = entries.filter((e: any) => e.day_of_week === d && e.period === p.label);
          if (dayEntries.length === 0) {
            cells += `<td style="padding:8px;vertical-align:top;border:1px solid #e2e8f0;min-width:120px;">&nbsp;</td>`;
          } else {
            const blocks = dayEntries.map((ent: any) => `
              <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:6px;padding:8px;margin-bottom:4px;font-size:11px;">
                <div style="font-weight:700;color:#4f46e5;margin-bottom:3px;">${ent.subject}</div>
                <div style="color:#64748b;font-size:10px;margin-bottom:2px;">${ent.teacher}</div>
                <div style="display:flex;justify-content:space-between;">
                  <span style="font-size:9px;font-weight:600;">${ent.room || ''}</span>
                  <span style="font-size:9px;color:#6366f1;">${ent.course}</span>
                </div>
              </div>
            `).join('');
            cells += `<td style="padding:8px;vertical-align:top;border:1px solid #e2e8f0;min-width:120px;">${blocks}</td>`;
          }
        }
        rows += `
          <tr>
            <td style="padding:10px;vertical-align:middle;border:1px solid #e2e8f0;background:#f8fafc;white-space:nowrap;">
              <div style="font-weight:600;font-size:13px;">${p.label}</div>
              <div style="font-size:10px;color:#64748b;">${p.start_time} - ${p.end_time}</div>
            </td>
            ${cells}
          </tr>
        `;
      }

      const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Master Schedule - Grid View</title>
<style>
  @page { size: landscape; margin: 12mm; }
  body { font-family: 'Inter', -apple-system, sans-serif; color: #1e293b; margin: 0; padding: 20px; }
  table { width: 100%; border-collapse: collapse; }
  @media print { body { padding: 0; } }
</style></head><body>
  <h2 style="margin:0 0 4px;font-size:20px;">Master Schedule</h2>
  ${filterLine}
  <table>
    <thead>
      <tr>
        <th style="padding:10px;text-align:left;background:#6366f1;color:white;border:1px solid #4f46e5;font-size:12px;">Period</th>
        ${daysShort.map(d => `<th style="padding:10px;text-align:center;background:#6366f1;color:white;border:1px solid #4f46e5;font-size:12px;">${d}</th>`).join('')}
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>
  <p style="margin-top:16px;font-size:10px;color:#94a3b8;">Generated on ${new Date().toLocaleString()}</p>
</body></html>`;

      const win = window.open('', '_blank');
      if (win) {
        win.document.write(html);
        win.document.close();
        setTimeout(() => win.print(), 300);
      }
      return;
    }

    // List view — use backend endpoint
    const token = localStorage.getItem('token');
    const params = new URLSearchParams();
    if (filters.session_id) params.append('session_id', filters.session_id);
    if (filters.course_id) params.append('course_id', filters.course_id);
    if (filters.semester_id) params.append('semester_id', filters.semester_id);
    if (filters.teacher_id) params.append('teacher_id', filters.teacher_id);

    try {
      const res = await axios.get(`http://localhost:8080/admin/timetable/export/html?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const win = window.open('', '_blank');
      if (win) {
        win.document.write(res.data);
        win.document.close();
        win.print();
      }
    } catch (e) { alert("Error exporting timetable"); }
  };

  const toggleDay = (day: number) => {
    const d = formData.days || [];
    if (d.includes(day)) setFormData({ ...formData, days: d.filter((x: number) => x !== day) });
    else setFormData({ ...formData, days: [...d, day] });
  };

  const daysLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const fullDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1>{isArchived ? 'Archived Classes' : 'Master Schedule'}</h1>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={handleExport} className="btn-secondary" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Download size={18} /> Export PDF
          </button>
          <div className="glass-card" style={{ padding: '4px', display: 'flex', gap: '5px' }}>
            <button onClick={() => setViewMode('list')} className={`btn-${viewMode === 'list' ? 'primary' : 'ghost'}`} style={{ padding: '8px 16px' }}>List View</button>
            <button onClick={() => setViewMode('grid')} className={`btn-${viewMode === 'grid' ? 'primary' : 'ghost'}`} style={{ padding: '8px 16px' }}>Grid View</button>
          </div>
        </div>
      </div>

      {!isArchived && (
        <div className="glass-card" style={{ padding: '20px', marginBottom: '30px', border: editingId ? '1px solid var(--primary)' : '1px solid var(--glass-border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
            <h3 style={{ margin: 0, color: 'var(--primary)' }}>{editingId ? 'Edit Timetable Entry' : 'Add Timetable Entries'}</h3>
            {editingId && (
              <button onClick={() => { setEditingId(null); setFormData({ session_id: '', course_id: '', semester_id: '', subject_id: '', teacher_user_id: '', room_id: '', period_id: '', days: [] }); }} className="btn-ghost" style={{ padding: '4px 10px', fontSize: '12px' }}>
                <X size={14} /> Cancel Edit
              </button>
            )}
          </div>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
            <select value={formData.session_id} onChange={e => setFormData({ ...formData, session_id: parseInt(e.target.value) })}>
              <option value="">Select Session Year</option>
              {lookups.sessions.map((s: any) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <select value={formData.course_id} onChange={e => setFormData({ ...formData, course_id: parseInt(e.target.value) })}>
              <option value="">Select Course</option>
              {lookups.courses.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select value={formData.semester_id} onChange={e => setFormData({ ...formData, semester_id: parseInt(e.target.value) })}>
              <option value="">Select Semester</option>
              {lookups.semesters.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select value={formData.subject_id} onChange={e => setFormData({ ...formData, subject_id: parseInt(e.target.value) })}>
              <option value="">Select Subject</option>
              {lookups.subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select value={formData.teacher_user_id} onChange={e => setFormData({ ...formData, teacher_user_id: parseInt(e.target.value) })}>
              <option value="">Select Teacher</option>
              {lookups.teachers.map((s: any) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
            </select>
            <select value={formData.room_id} onChange={e => setFormData({ ...formData, room_id: parseInt(e.target.value) })}>
              <option value="">Room (Optional)</option>
              {lookups.rooms.map((s: any) => <option key={s.id} value={s.id}>{s.name} - {s.building}</option>)}
            </select>
            <select value={formData.period_id} onChange={e => setFormData({ ...formData, period_id: parseInt(e.target.value) })}>
              <option value="">Select Period</option>
              {lookups.periods.map((s: any) => <option key={s.id} value={s.id}>{s.label} ({s.start_time} - {s.end_time})</option>)}
            </select>
  
            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--gray)' }}>{editingId ? 'Scheduled Day:' : 'Scheduled Days:'}</span>
              <div style={{ display: 'flex', gap: '5px' }}>
                {daysLabels.map((d, i) => (
                  <button key={i} type="button"
                    onClick={() => editingId ? setFormData({ ...formData, days: [i] }) : toggleDay(i)}
                    className={formData.days?.includes(i) ? 'btn-primary' : 'btn-ghost'}
                    style={{ width: '38px', height: '38px', padding: 0, fontSize: '11px', borderRadius: '10px' }}>
                    {d}
                  </button>
                ))}
              </div>
            </div>
  
            <button type="submit" className="btn-primary" style={{ alignSelf: 'end', height: '42px' }}>
              {editingId ? <Save size={18} /> : <Plus size={18} />} {editingId ? 'Update Slot' : 'Schedule Slot(s)'}
            </button>
          </form>
        </div>
      )}

      <div className="glass-card" style={{ padding: '20px', marginBottom: '20px', display: 'flex', flexWrap: 'wrap', gap: '15px', alignItems: 'center' }}>
        <Filter size={18} color="var(--primary)" />
        <span style={{ fontWeight: 600 }}>Filter View:</span>
        <select style={{ width: '150px' }} value={filters.session_id} onChange={e => setFilters({ ...filters, session_id: e.target.value })}>
          <option value="">All Sessions</option>
          {lookups.sessions.map((s: any) => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <select style={{ width: '150px' }} value={filters.course_id} onChange={e => setFilters({ ...filters, course_id: e.target.value })}>
          <option value="">All Courses</option>
          {lookups.courses.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select style={{ width: '150px' }} value={filters.semester_id} onChange={e => setFilters({ ...filters, semester_id: e.target.value })}>
          <option value="">All Semesters</option>
          {lookups.semesters.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select style={{ width: '150px' }} value={filters.teacher_id} onChange={e => setFilters({ ...filters, teacher_id: e.target.value })}>
          <option value="">All Teachers</option>
          {lookups.teachers.map((s: any) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
        </select>
        <button onClick={() => setFilters({ session_id: '', course_id: '', semester_id: '', teacher_id: '' })} className="btn-ghost" style={{ padding: '8px 12px', fontSize: '13px' }}>Reset</button>
      </div>

      {viewMode === 'list' ? (
        <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Time / Period</th>
                <th>Subject</th>
                <th>Teacher</th>
                <th>Course / Sem</th>
                <th>Room</th>
                <th style={{ width: '80px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((ent, i) => (
                <tr key={ent.id || i}>
                  <td style={{ fontWeight: 600 }}>{fullDays[ent.day_of_week]}</td>
                  <td><div style={{ fontSize: '13px' }}>{ent.time}</div><div style={{ fontSize: '11px', color: 'var(--gray)' }}>{ent.period}</div></td>
                  <td>{ent.subject}</td>
                  <td>{ent.teacher}</td>
                  <td><div style={{ fontSize: '11px' }}>{ent.course}</div><div style={{ fontSize: '10px', color: 'var(--gray)' }}>{ent.semester}</div></td>
                  <td>{ent.room}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {!isArchived ? (
                        <>
                          <button onClick={() => handleEdit(ent)} className="btn-ghost" style={{ padding: '6px', color: 'var(--primary)' }} title="Edit Slot"><Edit2 size={16} /></button>
                          <button onClick={() => handleArchive(ent.id)} className="btn-ghost" style={{ padding: '6px', color: 'var(--late)' }} title="Archive Slot"><Layer size={16} /></button>
                          <button onClick={() => handleDelete(ent.id)} className="btn-ghost" style={{ padding: '6px', color: '#ef4444' }} title="Delete Slot"><Trash2 size={16} /></button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => handleUnarchive(ent.id)} className="btn-ghost" style={{ padding: '6px', color: 'var(--primary)' }} title="Unarchive Slot"><Plus size={16} /></button>
                          <button onClick={() => handleDelete(ent.id)} className="btn-ghost" style={{ padding: '6px', color: '#ef4444' }} title="Delete Permanent"><Trash2 size={16} /></button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <TimetableGrid entries={entries} periods={lookups.periods} isArchivedView={isArchived} onArchive={handleArchive} onUnarchive={handleUnarchive} />
      )}
    </div>
  );
};

const TimetableGrid = ({ entries, periods, isArchivedView, onArchive, onUnarchive }: { entries: any[], periods: any[], isArchivedView: boolean, onArchive: (id: number) => void, onUnarchive: (id: number) => void }) => {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return (
    <div className="glass-card" style={{ padding: '20px', overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '8px' }}>
        <thead>
          <tr>
            <th style={{ minWidth: '100px' }}></th>
            {days.map(d => <th key={d} style={{ textAlign: 'center', color: 'var(--primary)', fontWeight: 700, padding: '10px' }}>{d}</th>)}
          </tr>
        </thead>
        <tbody>
          {periods.sort((a, b) => a.sort_order - b.sort_order).map(p => (
            <tr key={p.id}>
              <td style={{ verticalAlign: 'middle', borderRight: '1px solid rgba(0,0,0,0.06)', padding: '10px' }}>
                <div style={{ fontWeight: 600, fontSize: '14px' }}>{p.label}</div>
                <div style={{ fontSize: '11px', color: 'var(--gray)' }}>{p.start_time}-{p.end_time}</div>
              </td>
              {[0, 1, 2, 3, 4, 5, 6].map(d => {
                const dayEntries = entries.filter(e => e.day_of_week === d && e.period === p.label);
                return (
                  <td key={d} style={{ verticalAlign: 'top', minWidth: '140px' }}>
                    {dayEntries.map((ent, idx) => (
                      <div key={idx} style={{
                        background: 'rgba(99, 102, 241, 0.08)',
                        border: '1px solid rgba(99, 102, 241, 0.15)',
                        borderRadius: '8px',
                        padding: '10px',
                        marginBottom: '5px',
                        fontSize: '12px'
                      }}>
                        <div style={{ fontWeight: 700, color: 'var(--primary)', marginBottom: '4px' }}>{ent.subject}</div>
                        <div style={{ fontSize: '10px', color: 'var(--gray)', marginBottom: '2px' }}>{ent.teacher}</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '9px', fontWeight: 600 }}>{ent.room}</span>
                          <span style={{ fontSize: '9px', color: 'var(--primary)' }}>{ent.course.slice(0, 5)}...</span>
                        </div>
                        <div style={{ display: 'flex', gap: '5px', marginTop: '8px', borderTop: '1px solid rgba(0,0,0,0.05)', paddingTop: '5px' }}>
                           {isArchivedView ? (
                             <button onClick={() => onUnarchive(ent.id)} className="btn-ghost" style={{ padding: 0, color: 'var(--primary)' }} title="Unarchive"><Plus size={12} /></button>
                           ) : (
                             <button onClick={() => onArchive(ent.id)} className="btn-ghost" style={{ padding: 0, color: 'var(--late)' }} title="Archive"><Layer size={12} /></button>
                           )}
                        </div>
                      </div>
                    ))}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const AdminSettings = () => {
  const [geo, setGeo] = useState<any>({});
  const [sms, setSms] = useState<any>({});

  const fetchData = async () => {
    const token = localStorage.getItem('token');
    const h = { headers: { Authorization: `Bearer ${token}` } };
    const [g, s] = await Promise.all([
      axios.get('http://localhost:8080/admin/rules/geofence', h),
      axios.get('http://localhost:8080/admin/rules/sms', h)
    ]);
    setGeo(g.data);
    setSms(s.data);
  };

  useEffect(() => { fetchData(); }, []);

  const saveGeo = async () => {
    try {
      const token = localStorage.getItem('token');
      await axios.post('http://localhost:8080/admin/rules/geofence', geo, { headers: { Authorization: `Bearer ${token}` } });
      alert("Geofence saved");
    } catch (e) { alert("Error"); }
  };

  const saveSms = async () => {
    try {
      const token = localStorage.getItem('token');
      await axios.post('http://localhost:8080/admin/rules/sms', sms, { headers: { Authorization: `Bearer ${token}` } });
      alert("SMS saved");
    } catch (e) { alert("Error"); }
  };

  return (
    <div className="fade-in">
      <h1>Rules & Settings</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '30px', marginTop: '30px' }}>
        <div className="glass-card" style={{ padding: '30px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '25px' }}>
            <MapPin size={24} className="text-primary" />
            <h3 style={{ margin: 0 }}>Geofencing Policy</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--gray)' }}>Campus Latitude</label>
              <input type="number" step="0.000001" value={geo.lat || ''} onChange={e => setGeo({ ...geo, lat: parseFloat(e.target.value) })} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--gray)' }}>Campus Longitude</label>
              <input type="number" step="0.000001" value={geo.lng || ''} onChange={e => setGeo({ ...geo, lng: parseFloat(e.target.value) })} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--gray)' }}>Radius (Meters)</label>
              <input type="number" value={geo.radius || ''} onChange={e => setGeo({ ...geo, radius: parseInt(e.target.value) })} />
            </div>
            <button className="btn-primary" onClick={saveGeo}>Update Policy</button>
          </div>
        </div>

        <div className="glass-card" style={{ padding: '30px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '25px' }}>
            <MessageSquare size={24} className="text-primary" />
            <h3 style={{ margin: 0 }}>SMS Alerts (Twilio)</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
              <input type="checkbox" checked={sms.enabled || false} onChange={e => setSms({ ...sms, enabled: e.target.checked })} style={{ width: '20px' }} />
              Enable Automated Absence Alerts
            </label>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--gray)' }}>Twilio SID</label>
              <input value={sms.sid || ''} onChange={e => setSms({ ...sms, sid: e.target.value })} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--gray)' }}>Auth Token</label>
              <input type="password" value={sms.token || ''} onChange={e => setSms({ ...sms, token: e.target.value })} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--gray)' }}>From Number</label>
              <input value={sms.from_num || ''} onChange={e => setSms({ ...sms, from_num: e.target.value })} placeholder="+1555..." />
            </div>
            <button className="btn-primary" onClick={saveSms}>Save SMS Config</button>
          </div>
        </div>
      </div>
    </div>
  );
};



// Removed unused TeacherLessons component

const ManageBulkAttendance = () => {
  const [assignedClasses, setAssignedClasses] = useState<any[]>([]);
  const [selectedClassKey, setSelectedClassKey] = useState('');
  const [selectedMonths, setSelectedMonths] = useState<string[]>(() => {
    try {
      const today = new (NepaliDate as any)();
      const y = today.getYear();
      const m = (today.getMonth() + 1).toString().padStart(2, '0');
      return [`${y}-${m}`];
    } catch {
      return ["2081-12"]; // Fallback
    }
  });
  const [roster, setRoster] = useState<any[]>([]);
  const [attendance, setAttendance] = useState<Record<string, string>>({}); // Committed DB state
  const [pendingAttendance, setPendingAttendance] = useState<Record<string, string>>({}); // Unsaved local edits
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    const token = localStorage.getItem('token');
    const h = { headers: { Authorization: `Bearer ${token}` } };
    const classes = await axios.get('http://localhost:8080/teacher/schedule', h);
    setAssignedClasses(classes.data);
  };

  useEffect(() => { fetchData(); }, []);

  const fetchGrid = async () => {
    if (!selectedClassKey) return;
    setLoading(true);
    try {
      const [subjId] = selectedClassKey.split('__');
      const token = localStorage.getItem('token');
      const h = { headers: { Authorization: `Bearer ${token}` } };
      
      const rosterRes = await axios.get(`http://localhost:8080/teacher/roster/${subjId}`, h);
      setRoster(rosterRes.data);

      const months = [...selectedMonths].sort();
      if (months.length === 0) return;

      // Get the AD start of the first Nepali month and AD end of the last Nepali month
      const start = bsToAd(`${months[0]}-01`);
      
      const lastMonth = months[months.length - 1];
      const lastMonthParts = lastMonth.split('-').map(Number);
      const lastMonthDaysArray = getNepaliMonthDaysAD(lastMonthParts[0], lastMonthParts[1]);
      const lastMonthDays = lastMonthDaysArray.length;
      const end = bsToAd(`${lastMonth}-${lastMonthDays}`);

      const attRes = await axios.get(`http://localhost:8080/teacher/attendance/range?subject_id=${subjId}&start_date=${start}&end_date=${end}`, h);
      const newAtt: Record<string, string> = {};
      attRes.data.forEach((r: any) => {
        newAtt[`${r.student_user_id}_${r.attendance_date}`] = r.status;
      });
      setAttendance(newAtt);
      setPendingAttendance({}); // Reset pending on new fetch
    } catch (e) { alert("Error fetching grid data"); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchGrid(); }, [selectedClassKey, selectedMonths]);

  const updatePending = (studentId: number, date: string, status: string) => {
    const key = `${studentId}_${date}`;
    // If the new status matches the DB status, remove it from pending
    if (attendance[key] === status) {
      const newPending = { ...pendingAttendance };
      delete newPending[key];
      setPendingAttendance(newPending);
    } else {
      setPendingAttendance({ ...pendingAttendance, [key]: status });
    }
  };

  const handleBulkDateUpdate = (date: string, status: string) => {
    const newPending = { ...pendingAttendance };
    roster.forEach(s => {
      const key = `${s.id}_${date}`;
      if (attendance[key] !== status) {
        newPending[key] = status;
      } else {
        delete newPending[key];
      }
    });
    setPendingAttendance(newPending);
  };

  const handleSaveMonth = async (monthStr: string) => {
    if (!selectedClassKey) return;
    const [subjId, , perId] = selectedClassKey.split('__');
    const days = getDaysInMonth(monthStr);
    const records: any[] = [];
    
    roster.forEach(s => {
      days.forEach(d => {
        const key = `${s.id}_${d}`;
        if (pendingAttendance[key]) {
          records.push({
            student_id: s.id,
            subject_id: parseInt(subjId),
            period_id: parseInt(perId),
            date: d,
            status: pendingAttendance[key]
          });
        }
      });
    });

    if (records.length === 0) return alert("No changes to save for this month.");

    try {
      const token = localStorage.getItem('token');
      await axios.post('http://localhost:8080/attendance/bulk-mark', { records }, { headers: { Authorization: `Bearer ${token}` } });
      
      const newAtt = { ...attendance };
      const newPending = { ...pendingAttendance };
      records.forEach(r => {
        newAtt[`${r.student_id}_${r.date}`] = r.status;
        delete newPending[`${r.student_id}_${r.date}`];
      });
      setAttendance(newAtt);
      setPendingAttendance(newPending);
      alert(`Successfully saved ${records.length} records for ${new Date(monthStr + "-01").toLocaleDateString('default', { month: 'long' })}`);
    } catch (e) { alert("Error saving records."); }
  };

  const getDaysInMonth = (monthStr: string) => {
    const [year, month] = monthStr.split('-').map(Number);
    return getNepaliMonthDaysAD(year, month);
  };

  const currentClass = assignedClasses.find(c => `${c.subject_id}__${c.session_id}__${c.period_id}` === selectedClassKey);

  return (
    <div className="fade-in">
      <div className="print-header" style={{ display: 'none', borderBottom: '2px dotted #000', marginBottom: '20px', paddingBottom: '10px' }}>
        <h1 style={{ margin: '0 0 5px', fontSize: '20px' }}>Monthly Attendance Register</h1>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', fontSize: '12px' }}>
          <div>
            <strong>Subject:</strong> {currentClass?.subject_name} ({currentClass?.subject_code})<br/>
            <strong>Period:</strong> {currentClass?.period_label} ({currentClass?.start_time} - {currentClass?.end_time})
          </div>
          <div style={{ textAlign: 'right' }}>
            <strong>Teacher:</strong> {localStorage.getItem('user_full_name')}<br/>
            <strong>Session:</strong> {currentClass?.session_name || 'N/A'}<br/>
            <strong>Report Generated:</strong> {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }} className="noprint">
        <h1>Manage Bulk Attendance</h1>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => window.print()} className="btn-ghost"><Download size={18} /> Export PDF</button>
        </div>
      </div>

      <div className="glass-card noprint" style={{ padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>CLASS</label>
            <select value={selectedClassKey} onChange={e => setSelectedClassKey(e.target.value)}>
              <option value="">Select a class...</option>
              {assignedClasses.filter((v,i,a)=>a.findIndex(t=>(t.subject_id===v.subject_id && t.period_id===v.period_id))===i).map(c => (
                <option key={`${c.subject_id}__${c.session_id}__${c.period_id}`} value={`${c.subject_id}__${c.session_id}__${c.period_id}`}>
                  {c.subject_name} - {c.period_label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--gray)', marginBottom: '8px' }}>MONTHS</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {["2081-01", "2081-02", "2081-03", "2081-04", "2081-05", "2081-06", "2081-07", "2081-08", "2081-09", "2081-10", "2081-11", "2081-12"].map(m => (
                <button 
                  key={m} 
                  onClick={() => selectedMonths.includes(m) ? setSelectedMonths(selectedMonths.filter(x => x !== m)) : setSelectedMonths([...selectedMonths, m])}
                  className={`badge ${selectedMonths.includes(m) ? 'badge-present' : 'badge-absent'}`}
                  style={{ cursor: 'pointer', border: 'none' }}
                >
                  {NEPALI_MONTHS[parseInt(m.split('-')[1]) - 1]} {m.split('-')[0]}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="glass-card" style={{ padding: '40px', textAlign: 'center' }}>
          <p style={{ color: 'var(--primary)', fontWeight: 600 }}>Loading attendance grids...</p>
        </div>
      ) : !selectedClassKey ? (
        <div className="glass-card" style={{ padding: '80px 40px', textAlign: 'center', color: 'var(--gray)' }}>
          <Layer size={48} style={{ marginBottom: '16px', opacity: 0.3 }} />
          <p>Select a class and months above to view the attendance grid</p>
        </div>
      ) : roster.length === 0 ? (
        <div className="glass-card" style={{ padding: '80px 40px', textAlign: 'center', color: 'var(--gray)' }}>
          <Users size={48} style={{ marginBottom: '16px', opacity: 0.3 }} />
          <p>No students are currently enrolled in this subject.</p>
        </div>
      ) : (
        <>
          <div className="multi-month-container">
            {[...selectedMonths].sort().map(monthStr => {
              const days = getDaysInMonth(monthStr);
              const [y, m] = monthStr.split('-').map(Number);
              const monthLabel = `${NEPALI_MONTHS[m - 1]} ${y}`;
              const monthPendingCount = roster.reduce((count, s) => count + days.filter(d => pendingAttendance[`${s.id}_${d}`]).length, 0);

              return (
                <div key={monthStr} className="month-section glass-card" style={{ padding: 0, marginBottom: '24px', overflow: 'hidden', border: 'none' }}>
                  <div style={{ padding: '20px', borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(99, 102, 241, 0.03)' }}>
                    <h3 style={{ margin: 0 }}>{monthLabel}</h3>
                    <div className="noprint" style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                      {monthPendingCount > 0 && <span style={{ fontSize: '12px', color: 'var(--primary)', fontWeight: 600 }}>{monthPendingCount} unsaved changes</span>}
                      <button onClick={() => handleSaveMonth(monthStr)} className="btn-primary" style={{ padding: '8px 16px', fontSize: '13px' }} disabled={monthPendingCount === 0}>
                        <Save size={16} /> Save {NEPALI_MONTHS[parseInt(monthStr.split('-')[1]) - 1]} Records
                      </button>
                    </div>
                  </div>
                  <div style={{ overflowX: 'auto' }} className="table-wrapper">
                    <table className="bulk-grid-table" style={{ borderCollapse: 'collapse', width: '100%' }}>
                      <thead>
                        <tr>
                          <th className="fixed-col" style={{ background: '#f8fafc', position: 'sticky', left: 0, zIndex: 10, padding: '12px', border: '1px solid #e2e8f0' }}>Student</th>
                          {days.map(d => (
                              <th key={d} style={{ 
                              padding: '8px', border: '1px solid #e2e8f0', minWidth: '40px', fontSize: '10px', cursor: 'pointer',
                              background: (new Date(d).getDay() === 6) ? '#f1f5f9' : 'white' // Saturday is holiday in Nepal
                            }} onClick={() => {
                              const status = window.prompt(`Bulk mark all students for ${adToBs(d)}? (present/absent/late/excused)`);
                              if (status && ['present', 'absent', 'late', 'excused'].includes(status)) handleBulkDateUpdate(d, status);
                            }}>
                              {adToBs(d).split('-')[2]}<br/>{['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(d).getDay()]}
                            </th>
                          ))}
                          <th style={{ padding: '8px', border: '1px solid #e2e8f0', minWidth: '60px', fontSize: '10px', background: '#f8fafc' }}>Present</th>
                        </tr>
                      </thead>
                      <tbody>
                        {roster.map(s => {
                          const totalPresentInMonth = days.filter(d => (pendingAttendance[`${s.id}_${d}`] || attendance[`${s.id}_${d}`]) === 'present').length;
                          return (
                            <tr key={s.id}>
                              <td className="fixed-col" style={{ background: 'white', position: 'sticky', left: 0, zIndex: 5, padding: '10px', border: '1px solid #e2e8f0', fontWeight: 600, whiteSpace: 'nowrap' }}>{s.full_name}</td>
                              {days.map(d => {
                                const key = `${s.id}_${d}`;
                                const isPending = !!pendingAttendance[key];
                                const status = pendingAttendance[key] || attendance[key] || '';
                                const isWeekend = (new Date(d).getDay() === 0 || new Date(d).getDay() === 6);
                                const shortStatus = status ? status.charAt(0).toUpperCase() : '-';
                                return (
                                  <td key={d} style={{ 
                                    textAlign: 'center', padding: 0, border: '1px solid #e2e8f0',
                                    background: isPending ? 'rgba(99, 102, 241, 0.1)' : isWeekend ? '#f8fafc' : 'transparent'
                                  }}>
                                    <div className="status-cell" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                                      <select 
                                        className="noprint"
                                        value={status} onChange={e => updatePending(s.id, d, e.target.value)}
                                        style={{ border: 'none', width: '100%', height: '100%', padding: '8px 2px', background: 'transparent', fontSize: '12px', fontWeight: isPending ? 'bold' : 'normal', textAlign: 'center',
                                          color: status === 'present' ? '#059669' : status === 'absent' ? '#dc2626' : status === 'late' ? '#d97706' : status === 'excused' ? '#6366f1' : '#94a3b8',
                                          cursor: 'pointer'
                                        }}
                                      >
                                        <option value="">-</option>
                                        <option value="present">P</option>
                                        <option value="absent">A</option>
                                        <option value="late">L</option>
                                        <option value="excused">E</option>
                                      </select>
                                      <span className="print-only" style={{ fontSize: '12px', fontWeight: 'bold' }}>{shortStatus}</span>
                                    </div>
                                  </td>
                                );
                              })}
                              <td style={{ textAlign: 'center', padding: '10px', border: '1px solid #e2e8f0', fontWeight: 700, fontSize: '14px', color: 'var(--primary)', background: 'rgba(99, 102, 241, 0.05)' }}>
                                {totalPresentInMonth}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })}
          </div>

          {/* PDF Summary Table */}
          <div className="print-only" style={{ marginTop: '30px', pageBreakBefore: 'auto' }}>
            <h3 style={{ borderBottom: '2px solid #333', paddingBottom: '8px', marginBottom: '16px' }}>Cumulative Attendance Performance Summary</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9' }}>
                  <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Roll No</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>Student Name</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center' }}>Total Working Days</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center' }}>Present Days</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center' }}>Percentage</th>
                </tr>
              </thead>
              <tbody>
                {roster.map(s => {
                  const totalDays = selectedMonths.reduce((sum, m) => sum + getDaysInMonth(m).length, 0);
                  const totalPresent = selectedMonths.reduce((sum, m) => {
                    const days = getDaysInMonth(m);
                    return sum + days.filter(d => (pendingAttendance[`${s.id}_${d}`] || attendance[`${s.id}_${d}`]) === 'present').length;
                  }, 0);
                  const percentage = totalDays > 0 ? ((totalPresent / totalDays) * 100).toFixed(1) : '0';
                  return (
                    <tr key={s.id}>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>{s.student_code}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px' }}>{s.full_name}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center' }}>{totalDays}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center' }}>{totalPresent}</td>
                      <td style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'center', fontWeight: 'bold', color: parseFloat(percentage) < 75 ? '#dc2626' : '#059669' }}>{percentage}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

    </div>
  );
};

const StudentScanner = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleScan = async (result: string) => {
    // We expect the QR code to just be the token itself
    if (loading) return;
    setLoading(true);
    try {
      const tokenStr = localStorage.getItem('token');
      await axios.post('http://localhost:8080/student/checkin', {
        token: result
      }, { headers: { Authorization: `Bearer ${tokenStr}` } });
      alert("✅ Successfully checked into the class!");
      navigate('/');
    } catch (e: any) {
      alert(e.response?.data?.detail || "Invalid or expired Class QR Code.");
    } finally {
      setTimeout(() => setLoading(false), 2000);
    }
  };

  return (
    <div className="fade-in">
      <h1>Scan Class QR</h1>
      <div className="glass-card" style={{ padding: '40px', textAlign: 'center', maxWidth: '500px', margin: '40px auto' }}>
        <p style={{ color: 'var(--gray)', marginBottom: '30px' }}>
          Point your camera at the QR code displayed by your teacher to instantly mark your attendance for this period.
        </p>
        <div style={{ borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(99, 102, 241, 0.2)', background: 'rgba(0,0,0,0.05)' }}>
          <QRScanner onResult={handleScan} />
        </div>
        {loading && <p style={{ marginTop: '20px', color: 'var(--primary)', fontWeight: 'bold' }}>Recording attendance...</p>}
      </div>
    </div>
  );
};

const StudentLeave = () => {
  const [leaves, setLeaves] = useState<any[]>([]);
  const [formData, setFormData] = useState({ start_date: '', end_date: '', reason: '' });

  const fetchLeaves = async () => {
    const token = localStorage.getItem('token');
    const res = await axios.get('http://localhost:8080/student/leaves', { headers: { Authorization: `Bearer ${token}` } });
    setLeaves(res.data);
  };

  useEffect(() => { fetchLeaves(); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('token');
      // Convert BS input to AD for database
      const adData = {
        ...formData,
        start_date: bsToAd(formData.start_date),
        end_date: bsToAd(formData.end_date)
      };
      await axios.post('http://localhost:8080/student/leaves', adData, { headers: { Authorization: `Bearer ${token}` } });
      setFormData({ start_date: '', end_date: '', reason: '' });
      fetchLeaves();
    } catch (e) { alert("Error submitting request. Ensure dates are in YYYY-MM-DD format."); }
  };

  return (
    <div className="fade-in">
      <h1>Leave Requests</h1>
      <div className="glass-card" style={{ padding: '24px', marginBottom: '30px' }}>
        <form onSubmit={handleAdd} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>Start Date (BS)</label>
            <NepaliDatePicker value={formData.start_date} onChange={val => setFormData({ ...formData, start_date: val })} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>End Date (BS)</label>
            <NepaliDatePicker value={formData.end_date} onChange={val => setFormData({ ...formData, end_date: val })} />
          </div>
          <div style={{ flex: 2 }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--gray)' }}>Reason</label>
            <input required value={formData.reason} onChange={e => setFormData({ ...formData, reason: e.target.value })} placeholder="Personal reasons..." />
          </div>
          <button type="submit" className="btn-primary" style={{ height: '42px' }}><Plus size={18} /> Submit Request</button>
        </form>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Submitted At</th>
              <th>Dates Range</th>
              <th>Reason</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {leaves.map((l, i) => (
              <tr key={i}>
                <td>{adToBs(l.created_at.split('T')[0])}</td>
                <td>{adToBs(l.start_date)} to {adToBs(l.end_date)}</td>
                <td>{l.reason}</td>
                <td>
                  <span className={`badge ${l.status === 'approved' ? 'badge-present' : l.status === 'pending' ? 'badge-absent' : 'badge-danger'}`} style={{ opacity: l.status === 'pending' ? 0.6 : 1 }}>
                    {l.status.toUpperCase()}
                  </span>
                </td>
              </tr>
            ))}
            {leaves.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', padding: '40px', color: 'var(--gray)' }}>No leave requests found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const AdminLeaves = () => {
  const [leaves, setLeaves] = useState<any[]>([]);
  const fetchLeaves = async () => {
    const token = localStorage.getItem('token');
    const res = await axios.get('http://localhost:8080/admin/leaves', { headers: { Authorization: `Bearer ${token}` } });
    setLeaves(res.data);
  };

  useEffect(() => { fetchLeaves(); }, []);

  const handleReview = async (id: number, status: 'approved' | 'rejected') => {
    try {
      const token = localStorage.getItem('token');
      await axios.post('http://localhost:8080/admin/leave/review', { id, status }, { headers: { Authorization: `Bearer ${token}` } });
      alert(`Request ${status} successfully!`);
      fetchLeaves();
    } catch (e) { alert("Error updating request."); }
  };

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1>Review Leave Requests</h1>
        <div style={{ fontSize: '14px', color: 'var(--gray)' }}>{leaves.filter(l => l.status === 'pending').length} pending actions</div>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Student</th>
              <th>Date Range</th>
              <th>Reason</th>
              <th>Submitted</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {leaves.map((l) => (
              <tr key={l.id}>
                <td style={{ fontWeight: 600 }}>{l.student_name}</td>
                <td><div style={{ fontSize: '13px' }}>{adToBs(l.start_date)}</div><div style={{ fontSize: '11px', color: 'var(--gray)' }}>to {adToBs(l.end_date)}</div></td>
                <td style={{ maxWidth: '250px', fontSize: '13px' }}>{l.reason}</td>
                <td style={{ fontSize: '12px' }}>{adToBs(l.created_at.split('T')[0])}</td>
                <td>
                  <span className={`badge ${l.status === 'approved' ? 'badge-present' : l.status === 'pending' ? 'badge-absent' : 'badge-danger'}`}>
                    {l.status.toUpperCase()}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button 
                      onClick={() => {
                        if (l.status === 'approved') return;
                        if (window.confirm(`Are you sure you want to APPROVE ${l.student_name}'s leave request?`)) handleReview(l.id, 'approved');
                      }} 
                      className={l.status === 'approved' ? "btn-success" : "btn-primary"} 
                      style={{ padding: '6px 12px', fontSize: '12px', background: l.status === 'approved' ? 'var(--success)' : 'rgba(34, 197, 94, 0.1)', color: l.status === 'approved' ? 'white' : 'var(--success)', border: '1px solid var(--success)' }}
                    >
                      {l.status === 'approved' ? 'Approved' : 'Approve'}
                    </button>
                    <button 
                      onClick={() => {
                        if (l.status === 'rejected') return;
                        if (window.confirm(`Are you sure you want to REJECT ${l.student_name}'s leave request?`)) handleReview(l.id, 'rejected');
                      }} 
                      className="btn-ghost" 
                      style={{ padding: '6px 12px', fontSize: '12px', color: 'var(--danger)', background: l.status === 'rejected' ? 'rgba(239, 68, 68, 0.1)' : 'transparent', fontWeight: l.status === 'rejected' ? 700 : 400, border: l.status === 'rejected' ? '1px solid var(--danger)' : 'none' }}
                    >
                      {l.status === 'rejected' ? 'Rejected' : 'Reject'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {leaves.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', padding: '100px', color: 'var(--gray)' }}>All clear! No leave requests at the moment.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const App = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem('user');
    if (saved) setUser(JSON.parse(saved));
    setLoading(false);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    setUser(null);
  };

  if (loading) return <div style={{ color: 'var(--text)', display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>Initializing...</div>;

  return (
    <Router>
      {!user ? (
        <Routes>
          <Route path="/login" element={<LoginPage onLogin={setUser} />} />
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      ) : (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
          <Sidebar role={user.role} onLogout={handleLogout} />
          <main className="main-content" style={{ flex: 1, padding: '40px', overflowY: 'auto' }}>
            <Routes>
              <Route path="/" element={user.role === 'admin' ? <AdminDashboard /> : user.role === 'teacher' ? <TeacherDashboard /> : <h1>Welcome back, {user.full_name}</h1>} />
              <Route path="/attendance" element={user.role === 'admin' ? <AdminAttendance /> : <AttendanceMarking />} />
              <Route path="/admin/users" element={<AdminUsers />} />
              <Route path="/admin/sessions" element={<EntityManager title="Sessions" endpoint="sessions" columns={["Label", "Start Date (BS)", "End Date (BS)"]} fields={[{ name: 'label', label: 'Session Label', placeholder: '2081/2082' }, { name: 'start_date', label: 'Start Date (BS)', isDate: true }, { name: 'end_date', label: 'End Date (BS)', isDate: true }]} />} />
              <Route path="/admin/timetable" element={<AdminTimetable />} />
              <Route path="/admin/timetable/archived" element={<AdminTimetable isArchived={true} />} />
              <Route path="/admin/courses" element={<EntityManager title="Courses" endpoint="courses" columns={["Code", "Name"]} fields={[{ name: 'code', label: 'Course Code', placeholder: 'e.g. CS101' }, { name: 'name', label: 'Course Name', placeholder: 'e.g. Computer Science' }]} />} />
              <Route path="/admin/semesters" element={<EntityManager title="Semesters" endpoint="semesters" columns={["Name"]} fields={[{ name: 'name', label: 'Semester Name', placeholder: 'e.g. Semester 1' }]} />} />
              <Route path="/admin/subjects" element={<EntityManager title="Subjects" endpoint="subjects" columns={["Code", "Name"]} fields={[{ name: 'code', label: 'Subject Code', placeholder: 'e.g. MATH101' }, { name: 'name', label: 'Subject Name', placeholder: 'e.g. Calculus I' }]} />} />
              <Route path="/admin/rooms" element={<EntityManager title="Rooms" endpoint="rooms" columns={["Name", "Building"]} fields={[{ name: 'name', label: 'Room Name', placeholder: 'e.g. 101' }, { name: 'building', label: 'Building', placeholder: 'e.g. Science Block' }]} />} />
              <Route path="/admin/periods" element={<EntityManager title="Periods" endpoint="periods" columns={["Label", "Start", "End", "Order"]} fields={[{ name: 'label', label: 'Label', placeholder: 'P1' }, { name: 'start_time', label: 'Start', type: 'time' }, { name: 'end_time', label: 'End', type: 'time' }, { name: 'sort_order', label: 'Order', type: 'number' }]} />} />
              <Route path="/admin/compliance" element={<ComplianceExport />} />
              <Route path="/admin/leaves" element={<AdminLeaves />} />
              <Route path="/admin/settings" element={<AdminSettings />} />
              <Route path="/teacher/bulk-attendance" element={<ManageBulkAttendance />} />
              <Route path="/student/scan" element={<StudentScanner />} />
              <Route path="/student/reports" element={<StudentReports />} />
              <Route path="/student/leave" element={<StudentLeave />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </main>
        </div>
      )}
    </Router>
  );
};

export default App;
