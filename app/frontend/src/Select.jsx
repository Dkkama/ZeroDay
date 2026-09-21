export default function Select({ className = "", children, ...props }) {
  return (
    <span className="select-wrap">
      <select className={className} {...props}>{children}</select>
    </span>
  );
}
