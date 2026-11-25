from models.schemas import (
    ScrapeResult,
    ScrapedComment,
    ScrapedPost,
    ScrapedProfile,
    ScrapedVideo,
)


def test_nested_models_serialize_to_dicts():
    comment = ScrapedComment(text="Fictional comment", author="demo")
    post = ScrapedPost(platform="instagram", post_id="demo-1", comments=[comment])
    profile = ScrapedProfile(platform="instagram", username="demo", posts=[post])
    video = ScrapedVideo(platform="youtube", video_id="demo-2", views=12)
    result = ScrapeResult(
        platform="instagram", query="demo", profiles=[profile], videos=[video]
    )

    serialized = result.to_dict()
    assert serialized["profiles"][0]["posts"][0]["comments"] == [comment.to_dict()]
    assert serialized["videos"][0]["views"] == 12
    assert serialized["errors"] == []
    assert serialized["scraped_at"]


def test_mutable_defaults_are_independent():
    first = ScrapedPost(platform="twitter", post_id="first")
    second = ScrapedPost(platform="twitter", post_id="second")
    first.hashtags.append("demo")
    first.comments.append(ScrapedComment(text="Only on first"))
    assert second.hashtags == []
    assert second.comments == []

    first_result = ScrapeResult(platform="twitter", query="first")
    second_result = ScrapeResult(platform="twitter", query="second")
    first_result.errors.append("sample failure")
    assert second_result.errors == []
