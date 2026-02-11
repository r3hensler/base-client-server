import { useNavigate, Link } from "react-router-dom";
import { LoginForm } from "../components/LoginForm";

export function LoginPage() {
  const navigate = useNavigate();
  return (
    <div>
      <LoginForm onSuccess={() => navigate("/dashboard")} />
      <p>
        Don't have an account? <Link to="/register">Register</Link>
      </p>
    </div>
  );
}
