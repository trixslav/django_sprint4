from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, UpdateView
from django.http import Http404

from .forms import PostForm, CommentForm, UserEditForm
from .models import Category, Post, Comment

User = get_user_model()
POSTS_PER_PAGE = 10


def get_published_posts():
    return (
        Post.objects.select_related("category", "location", "author")
        .annotate(comment_count=Count("comments"))
        .filter(
            pub_date__lte=timezone.now(), is_published=True, category__is_published=True
        )
        .order_by("-pub_date")
    )


def index(request):
    posts = get_published_posts()
    paginator = Paginator(posts, POSTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "blog/index.html", {"page_obj": page_obj})


def post_detail(request, pk):
    posts_qs = Post.objects.select_related("author", "category", "location").annotate(
        comment_count=Count("comments")
    )
    post = get_object_or_404(posts_qs, pk=pk)

    if (
        not post.is_published
        or post.pub_date > timezone.now()
        or not post.category.is_published
    ):
        if request.user != post.author:
            raise Http404

    comments = post.comments.select_related("author")
    form = CommentForm()
    context = {
        "post": post,
        "form": form,
        "comments": comments,
    }
    return render(request, "blog/detail.html", context)


def category_posts(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug, is_published=True)
    posts = get_published_posts().filter(category=category)
    paginator = Paginator(posts, POSTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request, "blog/category.html", {"category": category, "page_obj": page_obj}
    )


def profile(request, username):
    author = get_object_or_404(User, username=username)

    if request.user == author:
        posts = author.posts.annotate(comment_count=Count("comments")).order_by(
            "-pub_date"
        )
    else:
        posts = get_published_posts().filter(author=author).order_by("-pub_date")

    paginator = Paginator(posts, POSTS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "profile": author,
        "page_obj": page_obj,
    }
    return render(request, "blog/profile.html", context)


@login_required
def edit_profile(request):
    form = UserEditForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect("blog:profile", username=request.user.username)
    return render(request, "blog/user.html", {"form": form})


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = "blog/create.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("blog:profile", kwargs={"username": self.request.user.username})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "blog/create.html"

    def test_func(self):
        return self.get_object().author == self.request.user

    def handle_no_permission(self):
        return redirect("blog:post_detail", pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("blog:post_detail", kwargs={"pk": self.kwargs["pk"]})


class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = "blog/create.html"

    def test_func(self):
        return self.get_object().author == self.request.user

    def get_success_url(self):
        return reverse("blog:profile", kwargs={"username": self.request.user.username})


@login_required
def add_comment(request, pk):
    post = get_object_or_404(Post, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect("blog:post_detail", pk=pk)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, author=request.user)
    form = CommentForm(request.POST or None, instance=comment)
    if form.is_valid():
        form.save()
        return redirect("blog:post_detail", pk=post_id)
    return render(request, "blog/comment.html", {"form": form, "comment": comment})


@login_required
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, author=request.user)
    if request.method == "POST":
        comment.delete()
        return redirect("blog:post_detail", pk=post_id)
    return render(request, "blog/comment.html", {"comment": comment})
