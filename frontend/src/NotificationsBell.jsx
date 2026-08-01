import { useState, useEffect } from "react";
import { getNotifications, markNotificationRead } from "./api";

export default function NotificationsBell() {
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  async function loadNotifications() {
    try {
      const data = await getNotifications(true);
      setNotifications(data.notifications || []);
    } catch (e) {
      // silent
    }
  }

  async function handleRead(id) {
    await markNotificationRead(id);
    loadNotifications();
  }

  const unread = notifications.filter((n) => !n.read).length;

  return (
    <div style={{ position: "relative" }}>
      <button
        className="nav-btn"
        onClick={() => setOpen(!open)}
        style={{ position: "relative" }}
      >
        🔔
        {unread > 0 && (
          <span style={{
            position: "absolute", top: -4, right: -4,
            background: "#ef4444", color: "#fff",
            borderRadius: "50%", width: 18, height: 18,
            fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div style={{
          position: "absolute", right: 0, top: 40, width: 360,
          background: "var(--bg-card)", border: "1px solid var(--border-color)",
          borderRadius: 12, padding: 12, zIndex: 100, maxHeight: 400, overflow: "auto",
          boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
        }}>
          <strong>Notifications</strong>
          {notifications.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 8 }}>No unread notifications</p>
          ) : (
            notifications.map((n) => (
              <div
                key={n.id}
                onClick={() => handleRead(n.id)}
                style={{
                  padding: 10, marginTop: 8, borderRadius: 8,
                  background: "rgba(99,102,241,0.08)", cursor: "pointer", fontSize: 13,
                }}
              >
                <strong>{n.title}</strong>
                <p style={{ margin: "4px 0 0", color: "var(--text-secondary)" }}>
                  {n.message?.slice(0, 120)}...
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
