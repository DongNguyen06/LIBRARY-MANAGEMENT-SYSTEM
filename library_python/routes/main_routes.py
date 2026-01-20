"""Main public routes for the library management system.

This module handles public-facing pages like home, search, and book details.
"""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from models.book import Book
from models.borrow import Borrow
from models.review import Review

# Create main blueprint
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    """Display the home page with featured books.
    
    Returns:
        Rendered home page template.
    """
    return render_template(
        'pages/home.html',
        new_arrivals=Book.get_new_arrivals(limit=4),
        most_borrowed=Book.get_most_borrowed(limit=4),
        top_rated=Book.get_top_rated(limit=4)
    )


@main_bp.route('/search')
def search():
    """Search for books with filters and sorting.
    
    Query parameters:
        q: Search query string
        searchBy: Field to search (title, author, category)
        sort: Sort order (title, author, year, rating, popular, new)
        category: Filter by category
    
    Returns:
        Rendered search results page.
    """
    query = request.args.get('q', '')
    search_by = request.args.get('searchBy', 'title')
    sort_by = request.args.get('sort', 'title')
    category = request.args.get('category', '')
    
    books = Book.search(query, search_by, sort_by, category)
    categories = Book.get_all_categories()
    
    return render_template(
        'pages/search.html',
        books=books,
        categories=categories,
        query=query,
        search_by=search_by,
        sort_by=sort_by,
        selected_category=category
    )


@main_bp.route('/book/<book_id>')
def book_detail(book_id: str):
    """Display detailed information about a specific book.
    
    Args:
        book_id: Unique identifier of the book.
    
    Returns:
        Rendered book detail page or redirect to search if not found.
    """
    book = Book.get_by_id(book_id)
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('main.search'))

    # Get reviews and calculate statistics
    review_objs = Review.get_by_book(book_id)
    reviews = [r.to_dict() for r in review_objs]
    
    # Calculate rating statistics
    if review_objs:
        avg_rating = round(sum(r.rating for r in review_objs) / len(review_objs), 1)
        distribution = {i: 0 for i in range(1, 6)}
        for r in review_objs:
            distribution[r.rating] += 1
        rating_stats = {
            'average': avg_rating,
            'count': len(review_objs),
            'distribution': distribution
        }
    else:
        rating_stats = {
            'average': 0,
            'count': 0,
            'distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        }

    # Default interaction status for guests
    interaction_status = {
        'is_favorite': False,
        'can_borrow': False,
        'can_reserve': False,
        'is_borrowed': False,
        'is_reserved': False,
        'can_review': False,
        'user_review': None
    }

    # Get interaction status for logged-in users
    if g.user and hasattr(g.user, 'id') and g.user.id:
        interaction_status = g.user.get_book_interaction_status(book_id, book)

    return render_template(
        'pages/book_detail.html',
        book=book,
        reviews=reviews,
        rating_stats=rating_stats,
        **interaction_status
    )


@main_bp.route('/chat')
def chat():
    """Display the chat interface.
    
    Note: This route requires login (handled by template).
    
    Returns:
        Rendered chat page template.
    """
    return render_template('pages/chat.html')