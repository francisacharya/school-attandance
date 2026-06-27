import React, { useEffect, useRef } from 'react';
import { Html5QrcodeScanner } from 'html5-qrcode';
import { Camera, AlertCircle } from 'lucide-react';

interface QRScannerProps {
  onResult: (result: string) => void;
}

const QRScanner: React.FC<QRScannerProps> = ({ onResult }) => {
  const scannerRef = useRef<Html5QrcodeScanner | null>(null);

  useEffect(() => {
    scannerRef.current = new Html5QrcodeScanner(
      "qr-reader",
      { fps: 10, qrbox: { width: 250, height: 250 } },
      /* verbose= */ false
    );

    scannerRef.current.render(
      (decodedText) => {
        onResult(decodedText);
      },
      (error) => {
        // Handle scan errors gracefully (e.g. log to console)
        // console.warn(`QR Scan error: ${error}`);
      }
    );

    return () => {
      if (scannerRef.current) {
        scannerRef.current.clear().catch(err => console.error("Error clearing scanner", err));
      }
    };
  }, [onResult]);

  return (
    <div className="glass-card fade-in" style={{ padding: '24px', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
        <Camera className="text-primary" size={24} />
        <h3 style={{ margin: 0 }}>QR Student Scanner</h3>
      </div>
      
      <div id="qr-reader" style={{ 
        width: '100%', 
        borderRadius: '12px', 
        overflow: 'hidden',
        border: '1px solid var(--glass-border)',
        background: 'rgba(0,0,0,0.2)'
      }}></div>
      
      <div style={{ marginTop: '20px', display: 'flex', gap: '10px', alignItems: 'start' }}>
        <AlertCircle size={16} style={{ color: 'var(--gray)', marginTop: '4px' }} />
        <p style={{ fontSize: '13px', color: 'var(--gray)', margin: 0 }}>
          Ensure the student's ID card or digital QR is clearly visible in the camera frame. 
          Scan result will be processed instantly.
        </p>
      </div>
    </div>
  );
};

export default QRScanner;
