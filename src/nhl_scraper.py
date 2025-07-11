import sys
import os
import pandas as pd
from nhlpy import NHLClient
import numpy as np
from collections import defaultdict
import itertools
import joblib

from src.config import MODELS_DIR
from src.config import DATA_DIR

def time_remaining(start_time_str, end_time_str):
    # Define total period as 20 minutes (1200 seconds)
    total_period_seconds = 20 * 60

    # Helper function to convert time string to total seconds
    def convert_to_seconds(time_str):
        minutes, seconds = map(int, time_str.split(":"))
        return minutes * 60 + seconds

    # Convert start and end times to seconds
    start_time_seconds = convert_to_seconds(start_time_str)
    end_time_seconds = convert_to_seconds(end_time_str)

    # Calculate remaining time by subtracting from 1200 seconds (20 minutes)
    start_remaining = total_period_seconds - start_time_seconds
    end_remaining = total_period_seconds - end_time_seconds

    # Helper function to convert seconds back to MM:SS format
    def convert_to_time_format(seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"

    # Convert remaining time back to MM:SS format
    start_remaining_time = convert_to_time_format(start_remaining)
    end_remaining_time = convert_to_time_format(end_remaining)

    return start_remaining_time, end_remaining_time


def time_to_seconds(time_str):
    # Split string on :
    mins, secs = time_str.split(":")
    total_sec = (int(mins) * 60) + int(secs)
    return total_sec


def seconds_to_time(total_sec):
    mins = total_sec // 60
    sec = total_sec % 60
    return f"{mins:02}:{sec:02}"


def second_diff(time1, time2):
    minutes1 = int(time1[0:2])
    minutes2 = int(time2[0:2])
    seconds1 = int(time1[3:5])
    seconds2 = int(time2[3:5])
    return abs((minutes2 * 60 + seconds2) - (minutes1 * 60 + seconds1))


def nhl_scraper(game_ids: list):

    client = NHLClient()
    shots = []
    blocks = []
    misses = []
    goals = []
    hits = []
    give_take = []
    faceoffs = []
    pens = []
    shifts = []
    players = []
    games = []
    teams = []

    conference_dict = {
        "FLA": "Eastern",
        "TOR": "Eastern",
        "TBL": "Eastern",
        "OTT": "Eastern",
        "DET": "Eastern",
        "MTL": "Eastern",
        "BOS": "Eastern",
        "BUF": "Eastern",
        "WSH": "Eastern",
        "CAR": "Eastern",
        "NJD": "Eastern",
        "CBJ": "Eastern",
        "NYR": "Eastern",
        "NYI": "Eastern",
        "PHI": "Eastern",
        "PIT": "Eastern",
        "WPG": "Western",
        "DAL": "Western",
        "MIN": "Western",
        "COL": "Western",
        "STL": "Western",
        "UTA": "Western",
        "NSH": "Western",
        "CHI": "Western",
        "VGK": "Western",
        "EDM": "Western",
        "CGY": "Western",
        "VAN": "Western",
        "ANA": "Western",
        "SEA": "Western",
        "SJS": "Western",
        "LAK": "Western",
    }

    division_dict = {
        "FLA": "Atlantic",
        "TOR": "Atlantic",
        "TBL": "Atlantic",
        "OTT": "Atlantic",
        "DET": "Atlantic",
        "MTL": "Atlantic",
        "BOS": "Atlantic",
        "BUF": "Atlantic",
        "WSH": "Metropolitan",
        "CAR": "Metropolitan",
        "NJD": "Metropolitan",
        "CBJ": "Metropolitan",
        "NYR": "Metropolitan",
        "NYI": "Metropolitan",
        "PHI": "Metropolitan",
        "PIT": "Metropolitan",
        "WPG": "Central",
        "DAL": "Central",
        "MIN": "Central",
        "COL": "Central",
        "STL": "Central",
        "UTA": "Central",
        "NSH": "Central",
        "CHI": "Central",
        "VGK": "Pacific",
        "EDM": "Pacific",
        "CGY": "Pacific",
        "VAN": "Pacific",
        "ANA": "Pacific",
        "SEA": "Pacific",
        "SJS": "Pacific",
        "LAK": "Pacific",
    }

    for game in game_ids:
        pbp = client.game_center.play_by_play(game_id=game)

        team_id_dict = {}
        home_id = pbp["homeTeam"]["id"]
        home_team = pbp["homeTeam"]["abbrev"]
        away_id = pbp["awayTeam"]["id"]
        away_team = pbp["awayTeam"]["abbrev"]
        team_id_dict[home_id] = home_team
        team_id_dict[away_id] = away_team
        h_city = pbp["homeTeam"]["placeName"]["default"]
        h_name = pbp["homeTeam"]["commonName"]["default"]
        h_conference = conference_dict[home_team]
        h_division = division_dict[home_team]
        a_city = pbp["awayTeam"]["placeName"]["default"]
        a_name = pbp["awayTeam"]["commonName"]["default"]
        a_conference = conference_dict[away_team]
        a_division = division_dict[away_team]

        if (home_id, home_team, h_city, h_name, h_conference, h_division) not in teams:
            teams.append((home_id, home_team, h_city, h_name, h_conference, h_division))

        if (
            away_id,
            away_team,
            a_city,
            a_name,
            a_conference,
            a_division,
        ) not in teams:
            teams.append((away_id, away_team, a_city, a_name, a_conference, a_division))

        box_score = client.game_center.boxscore(game)

        if "score" not in box_score["awayTeam"]:
            continue

        away_score = box_score["awayTeam"]["score"]
        home_score = box_score["homeTeam"]["score"]
        if home_score > away_score:
            winner = home_id
            loser = away_id
        else:
            winner = away_id
            loser = home_id

        games.append((game, away_id, away_score, home_id, home_score, winner, loser))

        rosters = {}
        for guy in pbp["rosterSpots"]:
            rosters[guy["playerId"]] = {
                "name": guy["firstName"]["default"] + " " + guy["lastName"]["default"],
                "position": guy["positionCode"],
                "jersey": guy["sweaterNumber"],
                "team": guy["teamId"],
            }

        shifts_list = client.game_center.shift_chart_data(game_id=game)["data"]

        for player in rosters.keys():
            if player not in players:
                name = rosters[player]["name"]
                position = rosters[player]["position"]
                team = rosters[player]["team"]
                players.append((player, name, team, position))

        for shift in shifts_list:
            start_time = shift["startTime"]
            end_time = shift["endTime"]
            player_id = shift["playerId"]
            shift_team_id = shift["teamId"]
            duration = shift["duration"]
            period = shift["period"]
            shifts.append(
                (
                    game,
                    home_id,
                    away_id,
                    shift_team_id,
                    period,
                    start_time,
                    end_time,
                    duration,
                    player_id,
                )
            )

        idx = -1

        for play in pbp["plays"]:
            idx += 1
            if play["typeDescKey"] in [
                "period-start",
                "period-end",
                "stoppage",
                "delayed-penalty",
                "game-end",
            ]:
                continue

            event_id = play["eventId"]
            period = play["periodDescriptor"]["number"]
            period_type = play["periodDescriptor"]["periodType"]
            time = play["timeRemaining"]

            away_goalie = play["situationCode"][0]
            away_skaters = play["situationCode"][1]
            home_skaters = play["situationCode"][2]
            home_goalie = play["situationCode"][3]

            if "details" not in play:
                continue

            event_owner = play["details"]["eventOwnerTeamId"]
            play_type = play["typeDescKey"]

            zone = play["details"]["zoneCode"]
            x = play["details"]["xCoord"]
            y = play["details"]["yCoord"]

            if (idx - 1) == -1:
                last_play = "Opening"
            else:
                last_play = pbp["plays"][idx - 1]["typeDescKey"]

            rebound = 0
            rush = 0

            if idx > 0:
                time_diff = second_diff(time, pbp["plays"][idx - 1]["timeInPeriod"])

                if (
                    pbp["plays"][idx - 1]["typeDescKey"] == "blocked-shot"
                    and time_diff <= 2
                ):
                    rebound = 1

                if (
                    pbp["plays"][idx - 1]["typeDescKey"]
                    in ["missed-shot", "shot-on-goal"]
                ) and time_diff <= 3:
                    rebound = 1

                if (
                    (pbp["plays"][idx - 1]["typeDescKey"] in ["takeaway", "giveaway"])
                    and time_diff <= 4
                    and pbp[idx - 1]["details"]["zoneCode"] in ["N", "D"]
                ):
                    rush = 1

            if "losingPlayerId" in play["details"]:
                win_player_id = play["details"]["winningPlayerId"]
                loss_player_id = play["details"]["losingPlayerId"]
                faceoffs.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        win_player_id,
                        loss_player_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif "hittingPlayerId" in play["details"]:
                hitter_id = play["details"]["hittingPlayerId"]
                hittee_id = play["details"]["hitteePlayerId"]
                hits.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        hitter_id,
                        hittee_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type in ["takeaway", "giveaway"]:
                player_id = play["details"]["playerId"]
                give_take.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        player_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "penalty":
                penalty_type = play["details"]["descKey"]
                if "drawnByPlayerId" not in play["details"]:
                    drawer_id = None
                else:
                    drawer_id = play["details"]["drawnByPlayerId"]
                if "committedByPlayerId" not in play["details"]:
                    guilty_id = None
                else:
                    guilty_id = play["details"]["committedByPlayerId"]
                duration = play["details"]["duration"]
                pens.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        penalty_type,
                        drawer_id,
                        guilty_id,
                        duration,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "shot-on-goal":
                shooter_id = play["details"]["shootingPlayerId"]
                goalie_id = play["details"]["goalieInNetId"]
                shot_type = play["details"]["shotType"]
                shots.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        rebound,
                        rush,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        shot_type,
                        shooter_id,
                        goalie_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "missed-shot":
                shooter_id = play["details"]["shootingPlayerId"]
                if "goalieInNetId" not in play["details"]:
                    goalie_id = None
                else:
                    goalie_id = play["details"]["goalieInNetId"]
                shot_type = play["details"]["shotType"]
                reason = play["details"]["reason"]
                misses.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        rebound,
                        rush,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        shot_type,
                        shooter_id,
                        goalie_id,
                        reason,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "goal":
                shooter_id = play["details"]["scoringPlayerId"]
                if "goalieInNetId" not in play["details"]:
                    goalie_id = None
                else:
                    goalie_id = play["details"]["goalieInNetId"]
                if "shotType" not in play["details"]:
                    shot_type = None
                else:
                    shot_type = play["details"]["shotType"]
                if "assist1PlayerTotal" in play["details"]:
                    primary_assist_id = play["details"]["assist1PlayerId"]
                    if "assist2PlayerId" in play["details"]:
                        secondary_assist_id = play["details"]["assist2PlayerId"]
                    else:
                        secondary_assist_id = None
                else:
                    primary_assist_id = None
                goals.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        rebound,
                        rush,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        shot_type,
                        shooter_id,
                        goalie_id,
                        primary_assist_id,
                        secondary_assist_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif "blocked-shot" == play_type:
                if "blockingPlayerId" not in play["details"]:
                    blocked_by_id = None
                else:
                    blocked_by_id = play["details"]["blockingPlayerId"]
                shooter_id = play["details"]["shootingPlayerId"]
                blocks.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        rebound,
                        rush,
                        last_play,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        blocked_by_id,
                        shooter_id,
                        x,
                        y,
                        zone,
                    )
                )
            else:
                continue

    shots_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "rebound",
        "rush",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "shot_type",
        "shooter_id",
        "goalie_id",
        "x",
        "y",
        "zone",
    ]
    blocks_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "rebound",
        "rush",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "blocked_by_id",
        "shooter_id",
        "x",
        "y",
        "zone",
    ]
    misses_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "rebound",
        "rush",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "shot_type",
        "shooter_id",
        "goalie_id",
        "reason",
        "x",
        "y",
        "zone",
    ]
    goals_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "rebound",
        "rush",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "shot_type",
        "shooter_id",
        "goalie_id",
        "primary_assist_id",
        "secondary_assist_id",
        "x",
        "y",
        "zone",
    ]
    hits_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "hitter_id",
        "hittee_id",
        "x",
        "y",
        "zone",
    ]
    give_take_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "player_id",
        "x",
        "y",
        "zone",
    ]
    faceoffs_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "win_player_id",
        "loss_player_id",
        "x",
        "y",
        "zone",
    ]
    pens_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "last_play",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "penalty_type",
        "drawer_id",
        "guilty_id",
        "duration",
        "x",
        "y",
        "zone",
    ]
    shifts_h = [
        "game",
        "home_id",
        "away_id",
        "shift_team",
        "period",
        "start_time",
        "end_time",
        "duration",
        "player_id",
    ]
    players_h = ["player_id", "name", "team", "position"]
    games_h = [
        "game",
        "away_id",
        "away_score",
        "home_id",
        "home_score",
        "winner",
        "loser",
    ]
    teams_h = ["team_id", "team_abbrev", "city", "name", "conference", "division"]

    shots_df = pd.DataFrame(shots, columns=shots_h)
    blocks_df = pd.DataFrame(blocks, columns=blocks_h)
    misses_df = pd.DataFrame(misses, columns=misses_h)
    goals_df = pd.DataFrame(goals, columns=goals_h)
    hits_df = pd.DataFrame(hits, columns=hits_h)
    give_take_df = pd.DataFrame(give_take, columns=give_take_h)
    faceoffs_df = pd.DataFrame(faceoffs, columns=faceoffs_h)
    pens_df = pd.DataFrame(pens, columns=pens_h)
    shifts_df = pd.DataFrame(shifts, columns=shifts_h)
    players_df = pd.DataFrame(players, columns=players_h)
    games_df = pd.DataFrame(games, columns=games_h)
    teams_df = pd.DataFrame(teams, columns=teams_h)

    return (
        shots_df,
        blocks_df,
        misses_df,
        goals_df,
        hits_df,
        give_take_df,
        faceoffs_df,
        pens_df,
        shifts_df,
        players_df,
        games_df,
        teams_df,
    )


def shot_scraper2(game_ids: list) -> pd.DataFrame:
    client = NHLClient()
    rows = []
    for game_id in game_ids:
        game_data = client.game_center.play_by_play(game_id=game_id)
        home_id = game_data["homeTeam"]["id"]
        away_id = game_data["awayTeam"]["id"]
        pbp = game_data["plays"]

        player_dict = {
            player["playerId"]: player["firstName"]["default"]
            + " "
            + player["lastName"]["default"]
            for player in game_data["rosterSpots"]
        }

        for idx, play in enumerate(pbp):

            if play["typeDescKey"] not in ["missed-shot", "goal", "shot-on-goal"]:
                continue

            home = 0
            away = 0
            rebound = 0
            rush = 0
            situation = play["situationCode"]

            try:
                if home_id == play["details"]["eventOwnerTeamId"]:
                    home = 1
                else:
                    away = 1

                if (home == 1 and situation[0] == "0") or (
                    away == 1 and situation[3] == "0"
                ):
                    continue

                if home == 1:
                    team_id = home_id
                else:
                    team_id = away_id

                if idx > 0:
                    time_diff = second_diff(
                        play["timeInPeriod"], pbp[idx - 1]["timeInPeriod"]
                    )

                    if pbp[idx - 1]["typeDescKey"] == "blocked-shot" and time_diff <= 2:
                        rebound = 1

                    if (
                        pbp[idx - 1]["typeDescKey"] in ["missed-shot", "shot-on-goal"]
                    ) and time_diff <= 3:
                        rebound = 1

                    if (
                        (pbp[idx - 1]["typeDescKey"] in ["takeaway", "giveaway"])
                        and time_diff <= 4
                        and pbp[idx - 1]["details"]["zoneCode"] in ["N", "D"]
                    ):
                        rush = 1

                home_skaters = play["situationCode"][2]
                away_skaters = play["situationCode"][1]
                shot_class = play["typeDescKey"]
                x_coord = abs(play["details"]["xCoord"])
                y_coord = play["details"]["yCoord"]
                shot_type = play["details"]["shotType"]
                shooter = None
                shooter_id = None
                goalie_id = play["details"]["goalieInNetId"]
                goalie = player_dict[goalie_id]
                last_play = pbp[idx - 1]["typeDescKey"]
                zone = play["details"]["zoneCode"]
                period = play["periodDescriptor"]["number"]
                time = play["timeInPeriod"]

                if shot_class == "goal":

                    shooter_id = play["details"]["scoringPlayerId"]
                    shooter = player_dict[shooter_id]

                else:

                    shooter_id = play["details"]["shootingPlayerId"]
                    shooter = player_dict[shooter_id]

                rows.append(
                    [
                        game_id,
                        team_id,
                        home,
                        last_play,
                        rebound,
                        rush,
                        home_skaters,
                        away_skaters,
                        x_coord,
                        y_coord,
                        shooter_id,
                        shooter,
                        goalie_id,
                        goalie,
                        shot_type,
                        zone,
                        shot_class,
                        period,
                        time,
                    ]
                )
            except:
                continue

    header = [
        "game_id",
        "team_id",
        "home",
        "last_play",
        "rebound",
        "rush",
        "home_skaters",
        "away_skaters",
        "x_coord",
        "y_coord",
        "shooter_id",
        "shooter",
        "goalie_id",
        "goalie",
        "shot_type",
        "zone",
        "shot_class",
        "period",
        "time",
    ]
    df = pd.DataFrame(rows, columns=header)
    return df.drop(["period", "time"], axis=1), df[["period", "time"]]


def get_skater_stats(df: pd.DataFrame) -> pd.DataFrame:

    client = NHLClient()
    stats_list = []
    goalie_stats = []
    stats_dict = {}
    goalie_stats_dict = {}

    shooter_ids = df["shooter_id"].tolist()
    goalie_ids = df["goalie_id"].tolist()

    for id in shooter_ids:
        if id not in stats_dict.keys():
            stats = client.stats.player_career_stats(id)
            try:
                stats_dict[id] = {
                    "position": stats["position"],
                    "hand": stats["shootsCatches"],
                    "pct": stats["featuredStats"]["regularSeason"]["career"][
                        "shootingPctg"
                    ],
                }
            except:
                stats_dict[id] = {
                    "position": stats["position"],
                    "hand": stats["shootsCatches"],
                    "pct": None,
                }

        position = stats_dict[id]["position"]
        shooter_hand = stats_dict[id]["hand"]
        shooting_pct = stats_dict[id]["pct"]
        stats_list.append((position, shooter_hand, shooting_pct))

    for id in goalie_ids:
        if id not in goalie_stats_dict.keys():
            stats = client.stats.player_career_stats(id)
            try:
                goalie_stats_dict[id] = {
                    "hand": stats["shootsCatches"],
                    "pct": stats["featuredStats"]["regularSeason"]["career"][
                        "savePctg"
                    ],
                }
            except:
                goalie_stats_dict[id] = {"hand": stats["shootsCatches"], "pct": None}

        shooter_hand = goalie_stats_dict[id]["hand"]
        save_pct = goalie_stats_dict[id]["pct"]
        goalie_stats.append((shooter_hand, save_pct))

    goalie_header = ["glove_hand", "save_pct"]
    goalie_df = pd.DataFrame(goalie_stats, columns=goalie_header)

    header = ["position", "shooter_hand", "shooting_pct"]
    stats_df = pd.DataFrame(stats_list, columns=header)

    final_df = pd.concat([df, stats_df, goalie_df], axis=1)
    return final_df


def angle(x_coord, y_coord):
    x_centered = 89 - x_coord
    return round(np.degrees(np.arctan(y_coord / x_centered)), 2)


def get_processed_data(df: pd.DataFrame) -> pd.DataFrame:
    df["angle"] = angle(df["x_coord"], df["y_coord"])
    df["shot_on_glove"] = df["shooter_hand"] + df["glove_hand"]
    df["home_skaters"] = df["home_skaters"].astype(int)
    df["away_skaters"] = df["away_skaters"].astype(int)
    df = df[df["home_skaters"] >= 3]
    df = df[df["away_skaters"] >= 3]
    df["situation"] = df.apply(
        lambda row: (
            "EV"
            if row["home_skaters"] == row["away_skaters"]
            else ("PP" if row["home_skaters"] > row["away_skaters"] else "SH")
        ),
        axis=1,
    )

    df = df.drop(
        ["game_id", "team_id", "shooter_id", "shooter", "goalie", "goalie_id"], axis=1
    )
    df["target"] = np.where(df["shot_class"] == "goal", 1, 0)

    home_mapping = {}
    home_mapping[0] = "Away"
    home_mapping[1] = "Home"

    rebound_mapping = {}
    rebound_mapping[0] = "No rebound"
    rebound_mapping[1] = "Rebound"

    rush_mapping = {}
    rush_mapping[0] = "No rush"
    rush_mapping[1] = "Rush"

    df["home"] = df["home"].replace(home_mapping)
    df["rebound"] = df["rebound"].replace(rebound_mapping)
    df["rush"] = df["rush"].replace(rush_mapping)

    df = df.drop("shot_class", axis=1)
    return df


def get_on_ice_players(shot_row, shifts_df):
    time = shot_row["game_seconds"]
    shifts_copy = shifts_df.copy()
    players_on_ice = shifts_copy[
        (shifts_copy["start_total_seconds"] <= time)
        & (shifts_copy["end_total_seconds"] >= time)
    ]

    home_id = shifts_copy["home_id"].iloc[0]
    away_id = shifts_copy["away_id"].iloc[0]

    home_players = players_on_ice[players_on_ice["shift_team"] == home_id][
        "player_id"
    ].tolist()
    away_players = players_on_ice[players_on_ice["shift_team"] == away_id][
        "player_id"
    ].tolist()

    return pd.Series({"home_players": home_players, "away_players": away_players})


def add_skaters_on_ice(
    processed_df: pd.DataFrame, time_df: pd.DataFrame, shifts_df: pd.DataFrame
) -> pd.DataFrame:
    shifts_copy = shifts_df.copy()
    final_df = processed_df.copy()
    final_df[["period", "time"]] = time_df
    final_df["time_seconds"] = final_df["time"].apply(time_to_seconds)
    final_df["game_seconds"] = (final_df["period"] - 1) * 1200 + final_df[
        "time_seconds"
    ]

    shifts_copy["start_seconds"] = shifts_copy["start_time"].apply(time_to_seconds)
    shifts_copy["end_seconds"] = shifts_copy["end_time"].apply(time_to_seconds)
    shifts_copy["start_total_seconds"] = (shifts_copy["period"] - 1) * 1200 + shifts_copy[
        "start_seconds"
    ]
    shifts_copy["end_total_seconds"] = (shifts_copy["period"] - 1) * 1200 + shifts_copy[
        "end_seconds"
    ]

    final_df[["home_players", "away_players"]] = final_df.apply(
        lambda row: get_on_ice_players(row, shifts_copy), axis=1
    )

    return final_df

def get_toi_df(shifts_df: pd.DataFrame, players_df: pd.DataFrame) -> pd.DataFrame:
    player_dict = dict(zip(players_df["player_id"].to_list(), players_df["name"].to_list()))
    new_shifts = shifts_df.copy()
    names = []

    for id in new_shifts["player_id"].to_list():
        name = player_dict[id]
        names.append(name)
    new_shifts["name"] = names
    new_shifts["duration"] = new_shifts["duration"].fillna("00:00")
    new_shifts["duration"] = new_shifts["duration"].apply(time_to_seconds)
    toi_df = new_shifts.groupby(["name", "period"])["duration"].sum()
    toi_df = toi_df.to_frame().reset_index()
    toi_df["duration_min"] = toi_df["duration"].apply(seconds_to_time)
    
    return toi_df

def get_attempts_df(
    shots_df: pd.DataFrame, misses_df: pd.DataFrame, blocks_df: pd.DataFrame, goals_df: pd.DataFrame
) -> pd.DataFrame:
    attempts_df = shots_df[["home_skaters", "away_skaters", "event_owner", "period", "time", "play_type", "shooter_id"]]
    attempts_df = pd.concat([attempts_df, misses_df[["home_skaters", "away_skaters", "event_owner", "period", "time", "play_type", "shooter_id"]]], axis=0)
    attempts_df = pd.concat([attempts_df, blocks_df[["home_skaters", "away_skaters", "event_owner", "period", "time", "play_type", "shooter_id"]]], axis=0)
    attempts_df = pd.concat([attempts_df, goals_df[["home_skaters", "away_skaters", "event_owner", "period", "time", "play_type", "shooter_id"]]], axis=0)
    attempts_df = attempts_df.sort_values(["period", "time"], ascending=[True, False]).reset_index(drop=True)
    return attempts_df

def get_corsi_df(attempts_df: pd.DataFrame, shifts_df: pd.DataFrame) -> pd.DataFrame:
    corsi_df = attempts_df.copy()
    shifts_copy = shifts_df.copy()

    shifts_copy["start_seconds"] = shifts_copy["start_time"].apply(time_to_seconds)
    shifts_copy["end_seconds"] = shifts_copy["end_time"].apply(time_to_seconds)
    shifts_copy["start_total_seconds"] = (shifts_copy["period"] - 1) * 1200 + shifts_copy[
        "start_seconds"
    ]
    shifts_copy["end_total_seconds"] = (shifts_copy["period"] - 1) * 1200 + shifts_copy[
        "end_seconds"
    ]

    corsi_df["tr_seconds"] = corsi_df["time"].apply(time_to_seconds)
    corsi_df["time_seconds"] = 1200 - corsi_df["tr_seconds"]
    corsi_df["game_seconds"] = (corsi_df["period"] - 1) * 1200 + corsi_df["time_seconds"]
    corsi_df[["home_players", "away_players"]] = corsi_df.apply(
        lambda row: get_on_ice_players(row, shifts_copy), axis=1
    )

    return corsi_df

def tally_xG(full_df: pd.DataFrame, players_df: pd.DataFrame) -> pd.DataFrame:
    xG_dict = {
        "xG_for": defaultdict(float),
        "xG_against": defaultdict(float)
    }

    for _, row in full_df.iterrows():
        xg = row["xG"]
        is_home_shot = row["home"]
        period = row["period"]

        if is_home_shot == "Home":
            shooting_team_players = row['home_players']
            defending_team_players = row['away_players']
        else:
            shooting_team_players = row['away_players']
            defending_team_players = row['home_players']

        for pid in shooting_team_players:
            xG_dict["xG_for"][(pid, period)] += xg
        for pid in defending_team_players:
            xG_dict["xG_against"][(pid, period)] += xg

    all_keys = set(xG_dict["xG_for"].keys()) | set(xG_dict["xG_against"].keys())
    final_df = pd.DataFrame([
        {
            "player_id": pid,
            "period": period,
            "xG_for": xG_dict["xG_for"].get((pid, period), 0.0),
            "xG_against": xG_dict["xG_against"].get((pid, period), 0.0)
        }
        for (pid, period) in all_keys
    ])
    return pd.merge(final_df, players_df, on="player_id", how="left").sort_values(by=["name", "period"], ascending=[True, True]).reset_index(drop=True)

def tally_corsi(corsi_df, players_df, game_id):
    client = NHLClient()

    pbp = client.game_center.play_by_play(game_id=game_id)
    home_id = pbp["homeTeam"]["id"]

    corsi_for = defaultdict(int)
    corsi_against = defaultdict(int)

    for _, row in corsi_df.iterrows():
        period = row["period"]
        if row["event_owner"] == home_id:
            for player in row["home_players"]:
                corsi_for[(player, period)] += 1
            for player in row["away_players"]:
                corsi_against[(player, period)] += 1
        else:
            for player in row["away_players"]:
                corsi_for[(player, period)] += 1
            for player in row["home_players"]:
                corsi_against[(player, period)] += 1

    all_keys = set(corsi_for.keys()) | set(corsi_against.keys())
    data = [
        {
        "player_id": player,
        "period": period,
        "corsi_for": corsi_for.get((player, period), 0),
        "corsi_against": corsi_against.get((player, period), 0)}
        for (player, period) in all_keys
    ]

    return pd.merge(pd.DataFrame(data), players_df, on="player_id", how="left").sort_values(by=["name", "period"], ascending=[True, True]).reset_index(drop=True)

def fill_shot_attempts(attempts_df: pd.DataFrame, players_df: pd.DataFrame) -> pd.DataFrame:
    attempts_by_period = attempts_df.groupby(["period","shooter_id"]).size().reset_index(name="total_attempts")
    all_players = attempts_df["shooter_id"].unique()
    all_periods = attempts_df["period"].unique()
    full_index = pd.DataFrame(itertools.product(all_players, all_periods), columns=["player_id", "period"])
    full_attempts = pd.merge(full_index, attempts_by_period, left_on=["player_id", "period"], right_on=["shooter_id", "period"], how="left").drop(columns=["shooter_id"])
    full_attempts["total_attempts"] = full_attempts["total_attempts"].fillna(0).astype(int)
    return pd.merge(full_attempts, players_df, on="player_id", how="left").sort_values(by=["name", "period"], ascending=[True, True]).reset_index(drop=True)

def get_box_score_dfs(game_id, players_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    client = NHLClient()
    box_score = client.game_center.boxscore(game_id)

    away_team_info = box_score["awayTeam"]
    away_team = away_team_info["abbrev"]
    away_score = away_team_info["score"]
    away_sog = away_team_info["sog"]

    home_team_info = box_score["homeTeam"]
    home_team = home_team_info["abbrev"]
    home_score = home_team_info["score"]
    home_sog = home_team_info["sog"]

    data = {
            "team": [away_team, home_team],
            "score": [away_score, home_score],
            "sog": [away_sog, home_sog]
            }

    score_df = pd.DataFrame(data)

    player_stats = box_score["playerByGameStats"]

    away_forward_stats = player_stats["awayTeam"]["forwards"]
    away_defense_stats = player_stats["awayTeam"]["defense"]
    away_goalie_stats = player_stats["awayTeam"]["goalies"]

    home_forward_stats = player_stats["homeTeam"]["forwards"]
    home_defense_stats = player_stats["homeTeam"]["defense"]
    home_goalie_stats = player_stats["homeTeam"]["goalies"]

    skater_rows = []
    goalie_rows = []

    for player in away_forward_stats:
        player_id = player["playerId"]
        goals = player["goals"]
        assists = player["assists"]
        points = player["points"]
        plus_minus = player["plusMinus"]
        pim = player["pim"]
        hits = player["hits"]
        pp_goals = player["powerPlayGoals"]
        sog = player["sog"]
        fo_pct = player["faceoffWinningPctg"]
        blocked_shots = player["blockedShots"]
        giveaways = player["giveaways"]
        takeaways = player["takeaways"]
        skater_rows.append((player_id, goals, assists, points, plus_minus, pim, hits, pp_goals, sog, fo_pct, blocked_shots, giveaways, takeaways))

    for player in away_defense_stats:
        player_id = player["playerId"]
        goals = player["goals"]
        assists = player["assists"]
        points = player["points"]
        plus_minus = player["plusMinus"]
        pim = player["pim"]
        hits = player["hits"]
        pp_goals = player["powerPlayGoals"]
        sog = player["sog"]
        fo_pct = player["faceoffWinningPctg"]
        blocked_shots = player["blockedShots"]
        giveaways = player["giveaways"]
        takeaways = player["takeaways"]
        skater_rows.append((player_id, goals, assists, points, plus_minus, pim, hits, pp_goals, sog, fo_pct, blocked_shots, giveaways, takeaways))

    for player in away_goalie_stats:
        player_id = player["playerId"]
        ga = player["goalsAgainst"]
        sa = player["shotsAgainst"]
        saves = player["saves"]
        goalie_rows.append((player_id, ga, sa, saves))

    for player in home_forward_stats:
        player_id = player["playerId"]
        goals = player["goals"]
        assists = player["assists"]
        points = player["points"]
        plus_minus = player["plusMinus"]
        pim = player["pim"]
        hits = player["hits"]
        pp_goals = player["powerPlayGoals"]
        sog = player["sog"]
        fo_pct = player["faceoffWinningPctg"]
        blocked_shots = player["blockedShots"]
        giveaways = player["giveaways"]
        takeaways = player["takeaways"]
        skater_rows.append((player_id, goals, assists, points, plus_minus, pim, hits, pp_goals, sog, fo_pct, blocked_shots, giveaways, takeaways))

    for player in home_defense_stats:
        player_id = player["playerId"]
        goals = player["goals"]
        assists = player["assists"]
        points = player["points"]
        plus_minus = player["plusMinus"]
        pim = player["pim"]
        hits = player["hits"]
        pp_goals = player["powerPlayGoals"]
        sog = player["sog"]
        fo_pct = player["faceoffWinningPctg"]
        blocked_shots = player["blockedShots"]
        giveaways = player["giveaways"]
        takeaways = player["takeaways"]
        skater_rows.append((player_id, goals, assists, points, plus_minus, pim, hits, pp_goals, sog, fo_pct, blocked_shots, giveaways, takeaways))

    for player in home_goalie_stats:
        player_id = player["playerId"]
        ga = player["goalsAgainst"]
        sa = player["shotsAgainst"]
        saves = player["saves"]
        goalie_rows.append((player_id, ga, sa, saves))

    skater_h = ["player_id", "goals", "assists", "points", "plus_minus", "pim", "hits", "pp_goals", "sog", "fo_pct", "blocked_shots", "giveaways", "takeaways"]
    goalie_h = ["player_id", "goals_against", "shots_against", "saves"]

    skater_box_score = pd.DataFrame(skater_rows, columns=skater_h)
    goalie_box_score = pd.DataFrame(goalie_rows, columns=goalie_h)

    goalie_box_score["save_pct"] = (goalie_box_score["saves"] / goalie_box_score["shots_against"]).round(3)

    skater_box_score = pd.merge(pd.merge(skater_box_score, players_df, how="left", on="player_id"), teams_df, left_on="team", right_on="team_id", how="left")
    goalie_box_score = pd.merge(pd.merge(goalie_box_score, players_df, how="left", on="player_id"), teams_df, left_on="team", right_on="team_id", how="left")

    return score_df, skater_box_score, goalie_box_score

def get_and_save_data_for_tableau(game_id):
    sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
    shots_df,blocks_df,misses_df,goals_df,_,_,_,_,shifts_df,players_df,_,teams_df = nhl_scraper([game_id])
    model = joblib.load(MODELS_DIR / "xgb_v1.pkl")

    temp_df, time_df = shot_scraper2([game_id])
    temp_df = get_skater_stats(temp_df)
    processed_df = get_processed_data(temp_df)

    full_shots_df = add_skaters_on_ice(processed_df, time_df, shifts_df)
    preds = model.predict_proba(full_shots_df.drop(['period', 'time', 'time_seconds', 'game_seconds',
        'home_players', 'away_players'], axis=1))
    xG = preds[:,1]
    full_shots_df["xG"] = xG

    xG_totals = tally_xG(full_shots_df, players_df)
    xG_totals["xGF%"] = xG_totals["xG_for"] / (xG_totals["xG_for"] + xG_totals["xG_against"])

    attempts_df = get_attempts_df(shots_df, misses_df, blocks_df, goals_df)
    full_attempts_df = fill_shot_attempts(attempts_df, players_df)
    corsi_df = get_corsi_df(attempts_df=attempts_df, shifts_df=shifts_df)
    corsi_totals = tally_corsi(corsi_df, players_df, game_id)

    corsi_totals["CF%"] = corsi_totals["corsi_for"] / (corsi_totals["corsi_for"] + corsi_totals["corsi_against"])
    xG_corsi_df = pd.merge(xG_totals, corsi_totals, how="outer", on=["name", "period"])

    final_df = pd.merge(
        xG_corsi_df,
        full_attempts_df,
        left_on=["player_id_x", "period"],
        right_on=["player_id", "period"],
        how="left"
    )

    final_df["total_attempts"] = final_df["total_attempts"].fillna(0).astype(int)
    final_df = final_df.drop(["player_id", "position_x", "position_y", "player_id_y", "name_y", "position", "team", "team_y"], axis=1)
    final_df.rename(columns={"player_id_x": "player_id", "name_x": "name", "team_x": "team"}, inplace=True)
    final_df = pd.merge(final_df, teams_df, left_on="team", right_on="team_id").drop("team", axis=1)

    final_df.to_csv(os.path.join(DATA_DIR, f"{game_id}_shot_info.csv"), index=False)
    print("Saved shot_info.csv!")

    toi_df = get_toi_df(shifts_df=shifts_df, players_df=players_df)
    toi_df.to_csv(os.path.join(DATA_DIR, f"{game_id}_toi_info.csv"), index=False)
    print("Saved toi_info.csv!")

    score_df, skater_box_score, goalie_box_score = get_box_score_dfs(game_id=game_id, players_df=players_df, teams_df=teams_df)

    score_df.to_csv(os.path.join(DATA_DIR, f"{game_id}_score_info.csv"), index=False)
    print("Saved score_info.csv!")

    skater_box_score.to_csv(os.path.join(DATA_DIR, f"{game_id}_skater_box_info.csv"), index=False)
    print("Saved skater_box_info.csv!")

    goalie_box_score.to_csv(os.path.join(DATA_DIR, f"{game_id}_goalie_box_info.csv"), index=False)
    print("Saved goalie_box_info.csv!")

    full_shots_df.to_csv(os.path.join(DATA_DIR, f"{game_id}_shot_location_info.csv"), index=False)
    print("Saved shot_location_info.csv!")

    return final_df, toi_df, score_df, skater_box_score, goalie_box_score, full_shots_df