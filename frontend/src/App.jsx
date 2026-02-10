import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Header from "./components/Header";
import AskPanel from "./components/askpanel";
import Login from "./components/Login";
import TeamDashboard from "./components/TeamDashboard";
import ProtectedRoute from "./components/ProtectedRoute";
import Signup from "./components/Signup";
import Simulation from "./components/Simulation";
import "./styles.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Header />
        <Routes>
          {/* Public login/signup routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Demo / Simulation Route (Public or Protected, let's protect it) */}
          <Route
            path="/simulation"
            element={
              <ProtectedRoute>
                <Simulation />
              </ProtectedRoute>
            }
          />

          {/* User route: existing Ask panel (Protected) */}
          <Route
            path="/ask"
            element={
              <ProtectedRoute>
                <AskPanel />
              </ProtectedRoute>
            }
          />

          {/* Backend / team dashboard route (Protected) */}
          <Route
            path="/backend"
            element={
              <ProtectedRoute>
                <TeamDashboard />
              </ProtectedRoute>
            }
          />

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/ask" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
