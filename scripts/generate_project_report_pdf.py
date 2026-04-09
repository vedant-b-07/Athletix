from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from textwrap import wrap


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT = 48
RIGHT = 48
TOP = 64
BOTTOM = 54
CONTENT_WIDTH = PAGE_WIDTH - LEFT - RIGHT


def pdf_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


@dataclass
class PDFPage:
    commands: list[str] = field(default_factory=list)

    def add(self, command: str) -> None:
        self.commands.append(command)

    def text(self, x: float, y: float, text: str, size: int = 11, font: str = "F1") -> None:
        self.add(f"BT /{font} {size} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({pdf_escape(text)}) Tj ET")

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float = 1) -> None:
        self.add(f"{width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def rect(self, x: float, y: float, w: float, h: float, stroke: bool = True, fill_gray: float | None = None) -> None:
        if fill_gray is not None:
            self.add(f"{fill_gray:.2f} g {x:.2f} {y:.2f} {w:.2f} {h:.2f} re {'B' if stroke else 'f'} 0 g")
        else:
            self.add(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re {'S' if stroke else 'f'}")

    def circle(self, x: float, y: float, r: float, width: float = 1) -> None:
        c = 0.552284749831 * r
        self.add(
            f"{width:.2f} w {x+r:.2f} {y:.2f} m "
            f"{x+r:.2f} {y+c:.2f} {x+c:.2f} {y+r:.2f} {x:.2f} {y+r:.2f} c "
            f"{x-c:.2f} {y+r:.2f} {x-r:.2f} {y+c:.2f} {x-r:.2f} {y:.2f} c "
            f"{x-r:.2f} {y-c:.2f} {x-c:.2f} {y-r:.2f} {x:.2f} {y-r:.2f} c "
            f"{x+c:.2f} {y-r:.2f} {x+r:.2f} {y-c:.2f} {x+r:.2f} {y:.2f} c S"
        )

    def ellipse(self, x: float, y: float, rx: float, ry: float, width: float = 1) -> None:
        c = 0.552284749831
        ox = rx * c
        oy = ry * c
        self.add(
            f"{width:.2f} w {x+rx:.2f} {y:.2f} m "
            f"{x+rx:.2f} {y+oy:.2f} {x+ox:.2f} {y+ry:.2f} {x:.2f} {y+ry:.2f} c "
            f"{x-ox:.2f} {y+ry:.2f} {x-rx:.2f} {y+oy:.2f} {x-rx:.2f} {y:.2f} c "
            f"{x-rx:.2f} {y-oy:.2f} {x-ox:.2f} {y-ry:.2f} {x:.2f} {y-ry:.2f} c "
            f"{x+ox:.2f} {y-ry:.2f} {x+rx:.2f} {y-oy:.2f} {x+rx:.2f} {y:.2f} c S"
        )

    def polygon(self, points: list[tuple[float, float]], stroke: bool = True, fill_gray: float | None = None) -> None:
        if not points:
            return
        cmds = [f"{points[0][0]:.2f} {points[0][1]:.2f} m"]
        for x, y in points[1:]:
            cmds.append(f"{x:.2f} {y:.2f} l")
        cmds.append("h")
        if fill_gray is not None:
            cmds.insert(0, f"{fill_gray:.2f} g")
            cmds.append("B" if stroke else "f")
            cmds.append("0 g")
        else:
            cmds.append("S" if stroke else "f")
        self.add(" ".join(cmds))


class SimplePDF:
    def __init__(self) -> None:
        self.pages: list[PDFPage] = []

    def new_page(self) -> PDFPage:
        page = PDFPage()
        self.pages.append(page)
        return page

    def save(self, path: Path) -> None:
        objects: list[bytes] = []

        def add_object(data: str | bytes) -> int:
            blob = data.encode("latin-1") if isinstance(data, str) else data
            objects.append(blob)
            return len(objects)

        font_regular = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        font_bold = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

        content_ids: list[int] = []
        page_ids: list[int] = []

        for page in self.pages:
            stream = "\n".join(page.commands) + "\n"
            content_id = add_object(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}endstream")
            content_ids.append(content_id)
            page_id = add_object("")
            page_ids.append(page_id)

        pages_id = add_object("")
        catalog_id = add_object("")

        for idx, page_id in enumerate(page_ids):
            page_dict = (
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> "
                f"/Contents {content_ids[idx]} 0 R >>"
            )
            objects[page_id - 1] = page_dict.encode("latin-1")

        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objects[pages_id - 1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode("latin-1")
        objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(f"{i} 0 obj\n".encode("latin-1"))
            out.extend(obj)
            out.extend(b"\nendobj\n")

        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        out.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
        out.extend(
            (
                f"trailer << /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF"
            ).encode("latin-1")
        )
        path.write_bytes(out)


def draw_header(page: PDFPage, title: str, subtitle: str | None = None) -> float:
    y = PAGE_HEIGHT - TOP
    page.text(LEFT, y, title, size=22, font="F2")
    page.line(LEFT, y - 8, PAGE_WIDTH - RIGHT, y - 8, width=1.4)
    if subtitle:
        page.text(LEFT, y - 28, subtitle, size=10)
        return y - 52
    return y - 32


def draw_footer(page: PDFPage, number: int) -> None:
    page.line(LEFT, BOTTOM - 8, PAGE_WIDTH - RIGHT, BOTTOM - 8, width=0.8)
    page.text(PAGE_WIDTH / 2 - 10, BOTTOM - 24, f"Page {number}", size=9)


def add_wrapped_paragraph(page: PDFPage, text: str, y: float, size: int = 11, leading: int = 15, indent: int = 0) -> float:
    width_chars = max(40, int((CONTENT_WIDTH - indent) / (size * 0.48)))
    for raw_line in text.split("\n"):
        lines = [""] if raw_line == "" else wrap(raw_line, width=width_chars)
        for line in lines:
            page.text(LEFT + indent, y, line, size=size)
            y -= leading
    return y


def add_bullets(page: PDFPage, items: list[str], y: float, size: int = 11, leading: int = 15) -> float:
    width_chars = max(40, int((CONTENT_WIDTH - 20) / (size * 0.48)))
    for item in items:
        wrapped = wrap(item, width=width_chars) or [item]
        for idx, line in enumerate(wrapped):
            prefix = "- " if idx == 0 else "  "
            page.text(LEFT, y, prefix + line, size=size)
            y -= leading
    return y


def add_table(page: PDFPage, x: float, y: float, widths: list[float], rows: list[list[str]], row_height: float = 28) -> float:
    for r, row in enumerate(rows):
        top = y - (r * row_height)
        current_x = x
        for c, cell in enumerate(row):
            shade = 0.90 if r == 0 else None
            page.rect(current_x, top - row_height, widths[c], row_height, fill_gray=shade)
            lines = wrap(cell, width=max(8, int(widths[c] / 6.0))) or [cell]
            text_y = top - 17
            for line in lines[:2]:
                page.text(current_x + 4, text_y, line, size=9, font="F2" if r == 0 else "F1")
                text_y -= 10
            current_x += widths[c]
    return y - (len(rows) * row_height) - 12


def draw_arrow(page: PDFPage, x1: float, y1: float, x2: float, y2: float) -> None:
    page.line(x1, y1, x2, y2, width=1)
    dx = x2 - x1
    dy = y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tip = (x2, y2)
    left = (x2 - 8 * ux + 4 * px, y2 - 8 * uy + 4 * py)
    right = (x2 - 8 * ux - 4 * px, y2 - 8 * uy - 4 * py)
    page.polygon([tip, left, right], stroke=True, fill_gray=0.0)


def use_case_diagram(page: PDFPage) -> None:
    y = draw_header(page, "Use Case Diagram", "Primary user interactions and backend-supported services")
    system_x = 180
    system_y = 160
    system_w = 340
    system_h = 520
    page.rect(system_x, system_y, system_w, system_h)
    page.text(system_x + 110, system_y + system_h - 22, "Athletix E-commerce System", size=14, font="F2")

    actor_x = 90
    actor_y = 560
    page.circle(actor_x, actor_y, 16)
    page.line(actor_x, actor_y - 16, actor_x, actor_y - 60)
    page.line(actor_x - 20, actor_y - 30, actor_x + 20, actor_y - 30)
    page.line(actor_x, actor_y - 60, actor_x - 16, actor_y - 92)
    page.line(actor_x, actor_y - 60, actor_x + 16, actor_y - 92)
    page.text(actor_x - 18, actor_y - 110, "Customer", size=11, font="F2")

    admin_x = 90
    admin_y = 250
    page.circle(admin_x, admin_y, 16)
    page.line(admin_x, admin_y - 16, admin_x, admin_y - 60)
    page.line(admin_x - 20, admin_y - 30, admin_x + 20, admin_y - 30)
    page.line(admin_x, admin_y - 60, admin_x - 16, admin_y - 92)
    page.line(admin_x, admin_y - 60, admin_x + 16, admin_y - 92)
    page.text(admin_x - 12, admin_y - 110, "Admin", size=11, font="F2")

    use_cases = [
        ("Register / Login", 285, 610),
        ("Browse Products", 285, 545),
        ("Search / Filter", 285, 480),
        ("Manage Cart", 285, 415),
        ("Manage Wishlist", 285, 350),
        ("Checkout & Pay", 285, 285),
        ("Track Orders", 285, 220),
        ("Update Order Status", 420, 220),
    ]

    for label, cx, cy in use_cases:
        page.ellipse(cx, cy, 82 if len(label) > 15 else 72, 24)
        page.text(cx - (len(label) * 2.7), cy - 4, label, size=10)

    for target in [(212, 610), (212, 545), (212, 480), (212, 415), (212, 350), (212, 285), (212, 220)]:
        draw_arrow(page, actor_x + 24, actor_y - 35, target[0], target[1])
    draw_arrow(page, admin_x + 24, admin_y - 35, 345, 220)
    draw_arrow(page, admin_x + 24, admin_y - 35, 348, 285)


def class_diagram(page: PDFPage) -> None:
    draw_header(page, "Class Diagram", "Core persistent entities and service abstractions")

    def class_box(x: float, y: float, w: float, h: float, name: str, attrs: list[str], ops: list[str]) -> None:
        page.rect(x, y, w, h)
        page.line(x, y + h - 24, x + w, y + h - 24)
        page.line(x, y + h - 84, x + w, y + h - 84)
        page.text(x + 8, y + h - 16, name, size=12, font="F2")
        ay = y + h - 40
        for attr in attrs[:4]:
            page.text(x + 8, ay, attr, size=9)
            ay -= 12
        oy = y + h - 102
        for op in ops[:4]:
            page.text(x + 8, oy, op, size=9)
            oy -= 12

    class_box(50, 520, 150, 190, "User", [
        "+ firebaseUid: String",
        "+ email: String",
        "+ addresses: Address[]",
        "+ lastLogin: Date",
    ], [
        "+ upsertUser()",
        "+ updateProfile()",
        "+ addAddress()",
        "+ setDefaultAddress()",
    ])
    class_box(230, 520, 150, 190, "Order", [
        "+ orderNumber: String",
        "+ total: Number",
        "+ paymentStatus: Enum",
        "+ orderStatus: Enum",
    ], [
        "+ createOrder()",
        "+ getMyOrders()",
        "+ getOrderById()",
        "+ updateOrderStatus()",
    ])
    class_box(410, 520, 140, 190, "Cart", [
        "+ userId: ObjectId",
        "+ productId: String",
        "+ quantity: Number",
        "+ selectedSize: String",
    ], [
        "+ getCart()",
        "+ addToCart()",
        "+ updateCartItem()",
        "+ clearCart()",
    ])
    class_box(100, 250, 160, 170, "Wishlist", [
        "+ userId: ObjectId",
        "+ productId: String",
        "+ createdAt: Date",
        "+ updatedAt: Date",
    ], [
        "+ getWishlist()",
        "+ addToWishlist()",
        "+ removeItem()",
        "+ syncUIState()",
    ])
    class_box(320, 250, 180, 170, "PaymentService", [
        "+ createRazorpayOrder()",
        "+ verifyPayment()",
        "+ uses Firebase token",
        "+ calls /api/payment/*",
    ], [
        "+ createOrder(amount)",
        "+ verifyPayment(data)",
        "+ getHeaders()",
        "+ handleResponse()",
    ])

    draw_arrow(page, 200, 615, 230, 615)
    draw_arrow(page, 380, 615, 410, 615)
    draw_arrow(page, 170, 420, 170, 520)
    draw_arrow(page, 410, 420, 410, 520)
    page.text(207, 625, "1 .. *", size=9)
    page.text(385, 625, "1 .. *", size=9)
    page.text(176, 470, "1 .. *", size=9)
    page.text(418, 470, "depends on", size=9)


def activity_diagram(page: PDFPage) -> None:
    draw_header(page, "Activity Diagram", "Checkout and payment workflow reflected in Checkout.jsx and backend APIs")

    def process_box(x: float, y: float, label: str) -> None:
        page.rect(x, y, 180, 38)
        page.text(x + 10, y + 15, label, size=10)

    def diamond(x: float, y: float, label: str) -> None:
        page.polygon([(x, y + 24), (x + 70, y), (x + 140, y + 24), (x + 70, y + 48)])
        page.text(x + 26, y + 20, label, size=9)

    page.circle(100, 710, 12)
    page.text(122, 705, "Start", size=10)
    process_box(60, 640, "Validate login and cart state")
    process_box(60, 565, "Select default or new address")
    diamond(50, 475, "Payment method?")
    process_box(40, 385, "Cash/UPI path: create local order")
    process_box(280, 385, "Razorpay path: create gateway order")
    process_box(280, 300, "Verify payment signature")
    diamond(250, 205, "Verified?")
    process_box(60, 120, "Persist order and clear cart")
    page.circle(150, 70, 12)
    page.text(170, 65, "End", size=10)

    draw_arrow(page, 100, 698, 100, 678)
    draw_arrow(page, 150, 640, 150, 603)
    draw_arrow(page, 150, 565, 150, 523)
    draw_arrow(page, 190, 499, 280, 404)
    draw_arrow(page, 120, 475, 120, 423)
    draw_arrow(page, 370, 385, 370, 338)
    draw_arrow(page, 370, 300, 370, 253)
    draw_arrow(page, 250, 229, 150, 158)
    draw_arrow(page, 150, 120, 150, 82)
    page.text(212, 440, "Razorpay", size=9)
    page.text(128, 440, "COD/alt", size=9)
    page.text(280, 190, "Yes", size=9)
    page.text(405, 218, "No -> show error", size=9)


def build_document(output_path: Path) -> None:
    pdf = SimplePDF()

    p = pdf.new_page()
    p.rect(36, 36, PAGE_WIDTH - 72, PAGE_HEIGHT - 72)
    p.text(80, 690, "ATHLETIX PROJECT REPORT", size=28, font="F2")
    p.text(80, 650, "Software Requirements Specification, UML Diagrams,", size=16)
    p.text(80, 628, "and Automated Testing Results", size=16)
    p.line(80, 608, 430, 608, width=1.5)
    p.text(80, 560, "Project Type: Premium sports e-commerce web application", size=13)
    p.text(80, 535, "Technology Stack: React 19, Vite 7, Firebase Auth, Express 5, MongoDB", size=13)
    p.text(80, 510, "Prepared From Repository Analysis", size=13)
    p.text(80, 485, "Workspace: C:\\Users\\hp\\ecomm", size=13)
    p.text(80, 460, "Prepared On: 2026-04-09", size=13)
    p.text(80, 180, "This report summarizes the implemented system, expected behavior,", size=12)
    p.text(80, 162, "data model, workflows, and the current automated verification status.", size=12)
    draw_footer(p, 1)

    p = pdf.new_page()
    y = draw_header(p, "Table of Contents", "15-page submission package")
    toc = [
        "1. Cover Page",
        "2. Table of Contents",
        "3. SRS: Introduction and Purpose",
        "4. SRS: Product Scope and Stakeholders",
        "5. SRS: Functional Requirements",
        "6. SRS: Non-functional Requirements",
        "7. SRS: Interfaces, Data, and Constraints",
        "8. Use Case Diagram",
        "9. Use Case Descriptions",
        "10. Class Diagram",
        "11. Class Responsibilities and Relationships",
        "12. Activity Diagram",
        "13. Activity Narrative and Exception Paths",
        "14. Automated Testing Results",
        "15. Risks, Conclusions, and Recommendations",
    ]
    y = add_bullets(p, toc, y, size=12, leading=28)
    draw_footer(p, 2)

    p = pdf.new_page()
    y = draw_header(p, "SRS: Introduction and Purpose", "Based on source analysis of the Athletix repository")
    y = add_wrapped_paragraph(
        p,
        "Athletix is a premium sports e-commerce platform that lets customers browse products, manage a cart and wishlist, authenticate with email or Google, maintain saved addresses, and place orders through an integrated checkout experience.",
        y,
    )
    y -= 8
    y = add_bullets(p, [
        "Purpose: define what the current application is expected to do from both user and developer viewpoints.",
        "Document scope: frontend routes, React context state, backend REST APIs, MongoDB models, Firebase-based authentication, and payment orchestration.",
        "Intended readers: project reviewers, developers, QA members, and academic evaluators expecting a compact SRS.",
        "System boundary: browser client, application backend, Firebase authentication provider, MongoDB persistence, and Razorpay payment integration.",
    ], y)
    y -= 6
    y = add_wrapped_paragraph(
        p,
        "Major frontend routes discovered in App.jsx are Home, Shop, Product Details, Cart, Checkout, Login, Register, Account, About, Contact, and Terms & Conditions. The backend exposes /api/users, /api/orders, /api/wishlist, /api/cart, and /api/payment.",
        y,
    )
    y -= 6
    y = add_table(p, LEFT, y, [120, 160, 220], [
        ["Aspect", "Observed Implementation", "Notes"],
        ["Client", "React SPA with Context providers", "Cart, auth, wishlist, and recommendation state"],
        ["Server", "Express application", "REST endpoints protected with Firebase token middleware"],
        ["Data", "MongoDB via Mongoose", "User, Order, Cart, and Wishlist models"],
        ["Payments", "Razorpay APIs", "Order creation and signature verification supported"],
    ])
    draw_footer(p, 3)

    p = pdf.new_page()
    y = draw_header(p, "SRS: Product Scope and Stakeholders")
    y = add_wrapped_paragraph(
        p,
        "The product targets customers purchasing athletic footwear, apparel, and sports accessories through a responsive web interface. The codebase also indicates an internal administrative role that can update order status, although no dedicated admin UI has been implemented in the frontend.",
        y,
    )
    y -= 8
    y = add_table(p, LEFT, y, [110, 140, 249], [
        ["Stakeholder", "Goal", "Relevant features"],
        ["Customer", "Discover and buy products", "Search, filter, product detail view, cart, wishlist, checkout"],
        ["Business owner", "Retain customers and process orders", "Persistent user records, address book, order history"],
        ["Operations/admin", "Track fulfillment", "Order retrieval and update status endpoints"],
        ["Developer", "Maintain and extend system", "Modular components, service layer, Mongoose models"],
    ], row_height=42)
    y -= 6
    y = add_bullets(p, [
        "Assumption: product catalog currently comes from static frontend data while transactional entities are persisted through the backend.",
        "Scope inclusion: authentication, account profile, address management, carting, wishlist, checkout, payment verification, and order retrieval.",
        "Scope exclusion: inventory management, product reviews, discount engine, admin dashboard UI, and automated unit/integration test suites.",
    ], y)
    draw_footer(p, 4)

    p = pdf.new_page()
    y = draw_header(p, "SRS: Functional Requirements")
    y = add_table(p, LEFT, y, [55, 190, 254], [
        ["ID", "Requirement", "Implementation evidence"],
        ["FR1", "The system shall allow a user to register or log in using email/password or Google sign-in.", "Auth.jsx and AuthContext.jsx use Firebase authentication and user upsert calls."],
        ["FR2", "The system shall allow browsing, filtering, and searching products.", "Shop.jsx uses query parameters, category filters, price range, brand filters, and search."],
        ["FR3", "The system shall allow users to add products to the cart and update quantities.", "CartContext.jsx and ProductDetails.jsx manage selected size, color, and quantity."],
        ["FR4", "The system shall allow users to maintain a wishlist.", "WishlistContext plus backend /api/wishlist endpoints support add/remove behavior."],
        ["FR5", "The system shall allow address creation and default address selection.", "User routes and AuthContext address methods support CRUD and default flagging."],
        ["FR6", "The system shall allow order placement and order history retrieval.", "Checkout.jsx, OrderService, and order routes support creation and retrieval."],
    ], row_height=52)
    draw_footer(p, 5)

    p = pdf.new_page()
    y = draw_header(p, "SRS: Non-functional Requirements")
    y = add_bullets(p, [
        "NFR1 Performance: the application should deliver SPA-style navigation and responsive filtering for catalog browsing. Vite production build completed successfully, indicating deployable asset generation.",
        "NFR2 Security: authenticated API operations require Firebase bearer tokens. The backend uses helmet, cors, and a token verification middleware.",
        "NFR3 Reliability: duplicate cart and wishlist entries are constrained through composite MongoDB indexes.",
        "NFR4 Usability: the UI includes recommendation widgets, product media viewers, toast notifications, and mobile navigation behavior.",
        "NFR5 Maintainability: the codebase separates pages, reusable components, context providers, service wrappers, and backend controllers/routes/models.",
        "NFR6 Scalability: current build warning shows a large JavaScript chunk, so future code-splitting is recommended for better production delivery.",
    ], y, leading=22)
    y -= 8
    y = add_wrapped_paragraph(
        p,
        "Constraints observed from the repository include dependency on Firebase project configuration, backend environment variables, MongoDB connectivity, and Razorpay credentials. Some fallback local state remains in contexts, so behavior may vary slightly between fully configured and demo-like sessions.",
        y,
    )
    draw_footer(p, 6)

    p = pdf.new_page()
    y = draw_header(p, "SRS: Interfaces, Data, and Constraints")
    y = add_table(p, LEFT, y, [110, 130, 259], [
        ["Interface", "Type", "Description"],
        ["Browser UI", "User interface", "React routes render shopping, account, checkout, and informational pages."],
        ["Firebase Auth", "External service", "Provides session state and ID tokens for protected backend calls."],
        ["REST API", "Application interface", "Client-side service layer calls /api/users, /api/orders, /api/cart, /api/wishlist, and /api/payment."],
        ["MongoDB", "Persistence", "Stores users with embedded addresses plus order, cart, and wishlist documents."],
    ], row_height=46)
    y -= 6
    y = add_bullets(p, [
        "Key data objects: User with embedded addresses, Order with embedded order items and shipping address, Cart item, Wishlist item.",
        "Primary identifiers: firebaseUid on the user profile, MongoDB _id for persistent entities, orderNumber for business-facing order reference.",
        "Business rule: cart uniqueness is enforced by userId + productId + selectedColor + selectedSize.",
        "Business rule: wishlist uniqueness is enforced by userId + productId.",
        "Constraint: the frontend catalog is data-driven from src/data/products.js rather than a backend product table.",
    ], y)
    draw_footer(p, 7)

    p = pdf.new_page()
    use_case_diagram(p)
    draw_footer(p, 8)

    p = pdf.new_page()
    y = draw_header(p, "Use Case Descriptions")
    y = add_table(p, LEFT, y, [110, 120, 269], [
        ["Use Case", "Primary Actor", "Summary"],
        ["Register/Login", "Customer", "Creates a Firebase-backed session and syncs the profile to backend storage."],
        ["Browse/Search", "Customer", "Views products, filters by category/brand/price, and searches by text."],
        ["Manage Cart", "Customer", "Adds configured items, edits quantity, applies coupon, and clears cart after purchase."],
        ["Manage Wishlist", "Customer", "Stores interesting products for later retrieval and toggles saved state from product cards."],
        ["Checkout & Pay", "Customer", "Selects address, chooses payment option, and either verifies Razorpay or creates a direct order."],
        ["Track Orders", "Customer", "Retrieves personal order history and order detail information."],
        ["Update Order Status", "Admin/Operations", "Changes backend order status for fulfillment progression."],
    ], row_height=50)
    y -= 4
    y = add_wrapped_paragraph(
        p,
        "Preconditions commonly include a valid authenticated user session, a non-empty cart for checkout, and network access to backend services. Postconditions include updated persistence records and refreshed local state in the corresponding React context.",
        y,
    )
    draw_footer(p, 9)

    p = pdf.new_page()
    class_diagram(p)
    draw_footer(p, 10)

    p = pdf.new_page()
    y = draw_header(p, "Class Responsibilities and Relationships")
    y = add_bullets(p, [
        "User aggregates address entries and acts as the root identity object mapped from Firebase authentication.",
        "Order belongs to exactly one user and embeds order items, shipping address, payment details, and fulfillment status fields.",
        "Cart stores transient purchase intent per user and distinguishes item variants using color and size.",
        "Wishlist stores saved product references and prevents duplicates for a user.",
        "Frontend service classes wrap HTTP requests, attach Firebase tokens, and normalize responses for React contexts.",
        "Controllers mediate between authenticated requests and Mongoose models, while routes define public API boundaries.",
    ], y, leading=22)
    y -= 8
    y = add_table(p, LEFT, y, [140, 120, 239], [
        ["Relationship", "Cardinality", "Meaning"],
        ["User -> Order", "1 to many", "A user may create multiple orders over time."],
        ["User -> Cart", "1 to many", "A user may hold multiple cart item variants simultaneously."],
        ["User -> Wishlist", "1 to many", "A user may bookmark multiple products."],
        ["Checkout -> PaymentService", "depends on", "Checkout delegates external payment orchestration to service methods."],
    ], row_height=42)
    draw_footer(p, 11)

    p = pdf.new_page()
    activity_diagram(p)
    draw_footer(p, 12)

    p = pdf.new_page()
    y = draw_header(p, "Activity Narrative and Exception Paths")
    y = add_wrapped_paragraph(
        p,
        "The checkout workflow begins when a logged-in user proceeds from the cart. Checkout.jsx validates session state, derives the default address if present, allows a new address to be added, and constructs order payloads with subtotal, shipping, tax, and total values.",
        y,
    )
    y -= 8
    y = add_bullets(p, [
        "If the user selects a non-gateway path, the frontend creates the order directly through the order service and clears the cart afterward.",
        "If the user selects Razorpay, the frontend loads the gateway script, requests a backend payment order, opens the payment modal, and verifies the resulting signature through /api/payment/verify.",
        "On successful verification, the order is persisted with payment details and the order confirmation state is displayed.",
        "If payment verification fails or the script cannot load, the flow surfaces an error and does not finalize the order.",
        "If the user is not authenticated or the cart is empty, navigation guards redirect the user or prevent progression.",
    ], y, leading=22)
    draw_footer(p, 13)

    p = pdf.new_page()
    y = draw_header(p, "Automated Testing Results", "Command-based verification executed on 2026-04-09")
    y = add_table(p, LEFT, y, [120, 90, 289], [
        ["Check", "Status", "Observed result"],
        ["npm run build", "PASS", "Production build completed successfully in 11.74s after rerunning outside sandbox. Vite warned that a generated JS chunk is 633.25 kB and should be split."],
        ["npm run lint", "FAIL", "ESLint reported 61 total findings: 55 errors and 6 warnings across frontend and backend files."],
        ["node --check backend/server.js", "PASS", "No syntax output was returned, indicating the backend entry file parsed successfully."],
        ["Sandbox note", "INFO", "Initial build failed in sandbox with Windows spawn EPERM; unrestricted rerun succeeded, so this was environmental rather than an application build error."],
    ], row_height=56)
    y -= 4
    y = add_bullets(p, [
        "Representative lint issues include undefined process references in backend files due to lint environment configuration.",
        "Several React files trigger react-hooks/set-state-in-effect rules because state is updated directly inside effects.",
        "Some components import unused motion helpers or keep unused local variables.",
        "MicroInteractions.jsx triggers purity warnings because Math.random is called during render.",
        "Context files trigger react-refresh/only-export-components warnings because component and non-component exports share a file.",
    ], y, leading=20)
    draw_footer(p, 14)

    p = pdf.new_page()
    y = draw_header(p, "Risks, Conclusions, and Recommendations")
    y = add_wrapped_paragraph(
        p,
        "The repository already implements a substantial end-to-end commerce flow with real authentication, persistence, and payment hooks. From an evaluation perspective, the project is strong on breadth and user-facing functionality, but the automated quality section shows maintainability issues that should be addressed before treating the codebase as production-ready.",
        y,
    )
    y -= 8
    y = add_bullets(p, [
        "Strength: complete customer journey across catalog, cart, account, checkout, and order retrieval.",
        "Strength: coherent backend route structure with Mongoose models and protected APIs.",
        "Risk: lint failures indicate code quality and React rule compliance debt.",
        "Risk: large frontend bundle may affect performance on slower connections.",
        "Recommendation: add a real automated test suite covering authentication flows, cart logic, checkout paths, and API controllers.",
        "Recommendation: introduce route-level code splitting, fix lint configuration for backend globals, and refactor effect-driven state updates.",
    ], y, leading=22)
    y -= 10
    y = add_wrapped_paragraph(
        p,
        "End of report.",
        y,
        size=13,
    )
    draw_footer(p, 15)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(output_path)


if __name__ == "__main__":
    build_document(Path("deliverables") / "Athletix_Project_Report_15_Pages.pdf")
