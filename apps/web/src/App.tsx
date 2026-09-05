import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch('/health', {
          method: 'GET',
          headers: {
            'Accept': 'application/json'
          }
        });
        const result = await response.json();
        setHealth(result);
      } catch (error: any) {
        console.error('Error fetching data:', error);
      }
    };
    fetchHealth();
  }, []);
  

  return (

    <div>
      <h1>EDLO</h1>
      <strong>Edlo's API Status: </strong>
      <div><span>Environment: </span>{health ? `🛠️ ${health.environment}` : "⚠️ Offline"}</div>
      <div><span>Server: </span>{health ? `🟢 ${health.status}` : "🔴 Offline"}</div>
  </div>
  )
}

interface HealthResponse {
  status: string;
  environment: string;
}

export default App
